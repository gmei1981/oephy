% nb_seed.m — seed1 vs seed7 逐源对照: 定位 342.8 vs 226.8fs 差异来自哪个源
%   solo runs at seed=1, mode2/K20, 对照 seed7 缓存值见文末注释
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
    'dco_pn_spec_f_hz',cfg0.dco_pn_spec_f_hz, 'dco_pn_spec_dbc',cfg0.dco_pn_spec_dbc, ...
    'dco_glitch_fs_per_code',0, 'ref_jitter_fs',0);
dsm_real = struct('dsm_fb_ideal',0, 'dtc_inl_lsb',2, 'dtc_dnl_lsb',1);
S1 = struct('seed',1);
runs = { ...
  'dco_s1',        as(ideal, S1); ...                                    % s7: 127.9
  'tdcq_m2_s1',    as(as(ideal,'dsm_fb_ideal',0),'tdc_ideal',0,'dsm_dco_mode',2, S1); ...   % s7: 148.8
  'dsmq_m2_s1',    as(as(merge(ideal,dsm_real),'tdc_ideal',0),'dsm_dco_mode',2, S1); ...    % s7: 206.5
  'tdcinlq_m2_s1', as(as(merge(ideal,dsm_real),'tdc_ideal',0),'tdc_inl_en',1,'dsm_dco_mode',2, S1); ... % s7: 189.8
  'dtc_s1',        as(as(ideal,'dtc_pn_floor_dbc',-160), S1)};             % s7: 79.6
fid = fopen(fullfile(top_dir,'output','noise_budget','seed1_solo.txt'),'w');
for k = 1:size(runs,1)
    key = runs{k,1}; odir = ['nb_' key]; over = runs{k,2};
    dmp = fullfile(top_dir,'output',odir,'DBG_phi_abs_err.txt');
    if exist(dmp,'file')==2
        e_full = readmatrix(dmp);
        c = regexp(fileread(fullfile(top_dir,'output',odir,'metrics.txt')), ...
            '(?m)^\s*lock_time_us:\s*([-\d.]+)','tokens','once');
        lock_us = str2double(c{1});
    else
        fprintf('===== seed1 solo %d/%d : %s =====\n', k, size(runs,1), key);
        R = top_adpll('default', as(over,'outdir_name',odir));
        e_full = R.phi_abs_err;
        lock_us = (find(R.phase_lock==1,1)-1)/fref*1e6;
    end
    i0 = max(ceil(1.5*(round(lock_us*1e-6*fref)+1)), i0min);
    e = detrend(e_full(i0:N), 1);
    [fk,Lk] = psd_phe(e, fref);
    sig = sqrt(2*trapz(fk(2:end),10.^(Lk(2:end)/10)))/(2*pi*fout)*1e15;
    fprintf('%16s : %8.1f %11.1f\n', key, lock_us, sig);
    fprintf(fid,'%s: lock_us=%.2f sigma_t_fs=%.1f\n', key, lock_us, sig);
end
fclose(fid);
fprintf('done\n');

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
