% nb_1bit.m (+ _b/_c) — 1-bit fbank architecture re-evaluation (2026-09-14).
%   fbank shrunk to a single cell of ONE abank LSB on a 1st-order SDM
%   (dsm_dco_mode=0) under the CURRENT framework: real DCO spec piecewise,
%   locked loop kp1=512/ki1=4 (fc 4.84 MHz, PM 62), clk_dsm = DCO/4 (K=20).
%   A: tot1b_s7/s1/s3 + tot1b_ng (no-glitch floor)
%   B: gl1b_s7/s1/s2/s3 (glitch solo @100 fs/code, seed spread)
%   C: gl1b_10/200/300 (glitch sweep) + dsmq_m0/tdcq_m0 (linear entries @K20)
%   Summary -> output/noise_budget/onebit_verify.txt.  Diagnostic only.
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
gl = @(fs) as(ideal, 'dco_glitch_fs_per_code',fs, 'dsm_dco_mode',0);
M0 = struct('dsm_dco_mode',0);

sfx = mfilename;
if endsWith(sfx,'_b')
  runs = { ...
    'gl1b_s7',  as(gl(100),'seed',7); ...
    'gl1b_s1',  as(gl(100),'seed',1); ...
    'gl1b_s2',  as(gl(100),'seed',2); ...
    'gl1b_s3',  as(gl(100),'seed',3)};
elseif endsWith(sfx,'_c')
  runs = { ...
    'gl1b_10',  as(gl(10), 'seed',7); ...
    'gl1b_200', as(gl(200),'seed',7); ...
    'gl1b_300', as(gl(300),'seed',7); ...
    'dsmq_m0',  as(as(merge(ideal,dsm_real),'tdc_ideal',0),'dsm_dco_mode',0); ...
    'tdcq_m0',  as(as(ideal,'dsm_fb_ideal',0),'tdc_ideal',0,'dsm_dco_mode',0)};
else
  runs = { ...
    'tot1b_s7', as(M0,'seed',7); ...
    'tot1b_s1', as(M0,'seed',1); ...
    'tot1b_s3', as(M0,'seed',3); ...
    'tot1b_ng', as(M0,'dco_glitch_fs_per_code',0,'seed',7)};
end

fid = fopen(fullfile(top_dir,'output','noise_budget','onebit_verify.txt'),'a');
for k = 1:size(runs,1)
    key = runs{k,1}; odir = ['nb_' key]; over = runs{k,2};
    dmp = fullfile(top_dir,'output',odir,'DBG_phi_abs_err.txt');
    if exist(dmp,'file')==2
        e_full = readmatrix(dmp);
        c = regexp(fileread(fullfile(top_dir,'output',odir,'metrics.txt')), ...
            '(?m)^\s*lock_time_us:\s*([-\d.]+)','tokens','once');
        lock_us = str2double(c{1});
    else
        fprintf('===== 1bit run %d/%d : %s =====\n', k, size(runs,1), key);
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
    % switching statistics from the DBG (mechanism table)
    dc = fullfile(top_dir,'output',odir,'DBG_dsm_code_dco.txt');
    if exist(dc,'file')==2
        c8v = readmatrix(dc);  c8 = round(c8v(i0:N));
        dst = abs(diff(c8)); sw = sum(dst>0);
        fprintf('   switches=%d rate=%.0fkHz mean|dstep|=%.2f\n', ...
            sw, sw/((N-i0)*1e-5)/1e3, mean(dst(dst>0)));
        fprintf(fid,'%s: switches=%d mean_dstep=%.2f\n', key, sw, mean(dst(dst>0)));
    end
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
