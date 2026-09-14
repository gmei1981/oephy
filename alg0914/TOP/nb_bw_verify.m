% nb_bw_verify.m — closed-loop verification of the analytic bandwidth sweep
%   (bw_sweep_probe.m): the linear-source optimum sits at fc ~ 2-3 MHz, so
%   run the REAL loop there — total (all sources, mode=2) and glitch-solo
%   runs, multi-seed because the glitch chatter is orbit roulette.
%   Cached dirs (DBG_phi_abs_err.txt present) are reused; delete to re-run.
%   Summary -> output/noise_budget/bw_verify.txt.  Diagnostic only.
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
gl100 = as(ideal, 'dco_glitch_fs_per_code', 100, 'dsm_dco_mode', 2);

BW2 = struct('kp1',213.7, 'ki1',0.417);          % fc~2.0M, PM~78 (bw_sweep_probe)
BW3 = struct('kp1',320.3, 'ki1',0.626);          % fc~3.0M, PM~73
runs = { ...
  'tot2m_s7', 'fc2M total s7', as(BW2,'dsm_dco_mode',2,'seed',7); ...
  'tot2m_s1', 'fc2M total s1', as(BW2,'dsm_dco_mode',2,'seed',1); ...
  'tot2m_s3', 'fc2M total s3', as(BW2,'dsm_dco_mode',2,'seed',3); ...
  'gl2m_s7',  'fc2M glitch100 s7', as(BW2, gl100, 'seed',7); ...
  'gl2m_s3',  'fc2M glitch100 s3', as(BW2, gl100, 'seed',3); ...
  'tot3m_s7', 'fc3M total s7', as(BW3,'dsm_dco_mode',2,'seed',7); ...
  'tot3m_s3', 'fc3M total s3', as(BW3,'dsm_dco_mode',2,'seed',3)};

fid = fopen(fullfile(top_dir,'output','noise_budget','bw_verify.txt'),'w');
fprintf('              key    lock_us  seg_us  sigma_t_fs  spur25dBc  chatter_x\n');
for k = 1:size(runs,1)
    key = runs{k,1}; odir = ['nb_' key]; over = runs{k,3};
    dmp = fullfile(top_dir,'output',odir,'DBG_phi_abs_err.txt');
    if exist(dmp,'file')==2
        e_full = readmatrix(dmp);
        mts = fileread(fullfile(top_dir,'output',odir,'metrics.txt'));
        c = regexp(mts,'(?m)^\s*lock_time_us:\s*([-\d.]+)','tokens','once');
        lock_us = str2double(c{1});
    else
        fprintf('===== run %d/%d : %s =====\n', k, size(runs,1), key);
        R = top_adpll('default', as(over,'outdir_name',odir));
        e_full = R.phi_abs_err;
        lock_us = (find(R.phase_lock==1,1)-1)/fref*1e6;
    end
    i0 = max(ceil(1.5*(round(lock_us*1e-6*fref)+1)), i0min);
    e = detrend(e_full(i0:N), 1);
    [fk,Lk] = psd_phe(e, fref);
    sig = sqrt(2*trapz(fk(2:end),10.^(Lk(2:end)/10)))/(2*pi*fout)*1e15;
    binw = fk(2)-fk(1);  spur25 = Lk(round(25e6/binw)+1);
    chat = sig/100 * (startsWith(key,'gl'));
    fprintf('%15s : %8.1f %7.0f %11.1f %10.1f %9.1f\n', key, lock_us, i0/fref*1e6, sig, spur25, chat);
    fprintf(fid,'%s: lock_us=%.2f seg_start_us=%.0f sigma_t_fs=%.1f spur25_dBc=%.2f chatter_x=%.1f\n', ...
        key, lock_us, i0/fref*1e6, sig, spur25, chat);
end
fclose(fid);
fprintf('\ndone -> output/noise_budget/bw_verify.txt\n');

function s = as(s,varargin)
q = 1;
while q <= numel(varargin)
    if isstruct(varargin{q})             % merge a struct of overrides in
        f = fieldnames(varargin{q});
        for j = 1:numel(f), s.(f{j}) = varargin{q}.(f{j}); end
        q = q + 1;
    else
        s.(varargin{q}) = varargin{q+1};
        q = q + 2;
    end
end
end
