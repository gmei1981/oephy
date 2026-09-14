% nb_impr.m (+_b) — 提升场景噪声预算 (2026-09-14 第六轮)
%   三项提升: ①DTC INL 逐码 LUT 预失真(残差 0.2 LSB) ②合成式 1/512 TDC
%   (白噪 σ=LSB/√12 + 标定后 INL 残差 0.25 LSB) ③DTC PN floor −165 dBc/Hz
%   基线: 实测 glitch 律 (mode2 0.67fs/code), fc=4.84M, K=20
%   A: impr_tot s7/s1/s3 + TDC512 solo
%   B: dsmq+LUT s7/s1 (泄漏重测+标定后轮盘) + dtc165 solo
top_dir = fileparts(mfilename('fullpath'));
addpath(fullfile(top_dir,'funcs_top'));
addpath(fullfile(top_dir,'..','funcs'));
cfg0 = read_cfg_txt(fullfile(top_dir,'cfg','top_cfg.txt'));
fref = cfg0.fref; fout = cfg0.adpll_fcw/2^35*fref; N = round(cfg0.n_cycles);
i0min = cfg0.inl_calib_start_cycle + 15000;

ideal = struct( ...
    'tdc_ideal',1, 'dsm_fb_ideal',1, 'tdc_inl_en',0, ...
    'dtc_inl_lsb',0, 'dtc_dnl_lsb',0, 'dtc_pn_floor_dbc',-300, ...
    'dco_pn_l1m_dbc',-300, 'dco_pn_floor_dbc',-300, 'dco_pn_rms_fs',0, ...
    'dco_pn_spec_f_hz','', 'dco_pn_spec_dbc','', ...
    'dco_glitch_fs_per_code',0, 'ref_jitter_fs',0);
dsm_real = struct('dsm_fb_ideal',0, 'dtc_inl_lsb',2, 'dtc_dnl_lsb',1);

% 提升场景的三块配置
LUT  = struct('dtc_inl_lut_calib_en',1, 'dtc_inl_lut_res_lsb',0.2);
T512 = struct('tdc_ideal',1, 'tdc_synth_lsb_cyc',1/512, 'tdc_synth_inl_lsb',0.25);
D165 = struct('dtc_pn_floor_dbc',-165);
M2G  = struct('dsm_dco_mode',2, 'dco_glitch_fs_per_code',0.67);

if endsWith(mfilename,'_b')
  runs = { ...
    'dsmqLUT_s7',  as(as(as(merge(ideal,dsm_real),LUT),'tdc_synth_lsb_cyc',1/512,'tdc_synth_inl_lsb',0.25),'seed',7); ...
    'dsmqLUT_s1',  as(as(as(merge(ideal,dsm_real),LUT),'tdc_synth_lsb_cyc',1/512,'tdc_synth_inl_lsb',0.25),'seed',1); ...
    'dtc165_s7',   as(as(ideal,D165),'seed',7)};
else
  runs = { ...
    'impr_tot_s7', as(merge(merge(merge(LUT,T512),D165), M2G), 'seed',7); ...
    'impr_tot_s1', as(merge(merge(merge(LUT,T512),D165), M2G), 'seed',1); ...
    'impr_tot_s3', as(merge(merge(merge(LUT,T512),D165), M2G), 'seed',3); ...
    'tdcq512_s7',  as(as(ideal,T512),'seed',7)};
end

fid = fopen(fullfile(top_dir,'output','noise_budget','impr_verify.txt'),'a');
for k = 1:size(runs,1)
    key = runs{k,1}; odir = ['nb_' key]; over = runs{k,2};
    dmp = fullfile(top_dir,'output',odir,'DBG_phi_abs_err.txt');
    if exist(dmp,'file')==2
        e_full = readmatrix(dmp);
        c = regexp(fileread(fullfile(top_dir,'output',odir,'metrics.txt')), ...
            '(?m)^\s*lock_time_us:\s*([-\d.]+)','tokens','once');
        lock_us = str2double(c{1});
    else
        fprintf('===== impr run %d/%d : %s =====\n', k, size(runs,1), key);
        R = top_adpll('default', as(over,'outdir_name',odir));
        e_full = R.phi_abs_err;
        lock_us = (find(R.phase_lock==1,1)-1)/fref*1e6;
    end
    i0 = max(ceil(1.5*(round(lock_us*1e-6*fref)+1)), i0min);
    e = detrend(e_full(i0:N), 1);
    [fk,Lk] = psd_phe(e, fref);
    sig = sqrt(2*trapz(fk(2:end),10.^(Lk(2:end)/10)))/(2*pi*fout)*1e15;
    binw = fk(2)-fk(1); spur25 = Lk(round(25e6/binw)+1);
    fprintf('%15s : %8.1f %11.1f %10.1f\n', key, lock_us, sig, spur25);
    fprintf(fid,'%s: lock_us=%.2f sigma_t_fs=%.1f spur25_dBc=%.2f\n', ...
        key, lock_us, sig, spur25);
end
fclose(fid);
fprintf('done (%s)\n', mfilename);

function s = as(s,varargin)
q = 1;
while q <= numel(varargin)
    if isstruct(varargin{q})
        f = fieldnames(varargin{q});
        for j = 1:numel(f), s.(f{j}) = varargin{q}.(f{j}); end
        q = q + 1;
    else
        s.(varargin{q}) = varargin{q+1};
        q = q + 2;
    end
end
end
function s = merge(a,b)
s = a;
f = fieldnames(b);
for q = 1:numel(f), s.(f{q}) = b.(f{q}); end
end
