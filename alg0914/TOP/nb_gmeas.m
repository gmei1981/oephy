% nb_gmeas.m (+_b) — noise budget with MEASURED glitch amplitudes (2026-09-14).
%   Silicon law (adpll_ted/sim/GLITCH_MEAS.md): kick = 91 fs/MHz x unit step.
%     mode2 3-bit unit  = 1/8 abank LSB = 7.339kHz  -> 0.67 fs/code
%     mode0 1-bit cell  = 1   abank LSB = 58.71kHz  -> 5.34 fs/code
%   Runs (current framework: real DCO spec, fc=4.84M, K=20):
%     A: totm2_g067 s7/s1 (all sources, mode2, 0.67) + glm2 solo 0.67
%     B: totm0_g53  s7/s1 (all sources, mode0, 5.34) + glm0 solo 5.34
%   Summary -> output/noise_budget/glitch_meas_verify.txt.  Diagnostic only.
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

if endsWith(mfilename,'_b')
  runs = { ...
    'totm0_g53_s7', as(struct('dsm_dco_mode',0,'dco_glitch_fs_per_code',5.34,'seed',7)); ...
    'totm0_g53_s1', as(struct('dsm_dco_mode',0,'dco_glitch_fs_per_code',5.34,'seed',1)); ...
    'glm0_53',      as(ideal,'dco_glitch_fs_per_code',5.34,'dsm_dco_mode',0,'seed',7)};
else
  runs = { ...
    'totm2_g067_s7', as(struct('dsm_dco_mode',2,'dco_glitch_fs_per_code',0.67,'seed',7)); ...
    'totm2_g067_s1', as(struct('dsm_dco_mode',2,'dco_glitch_fs_per_code',0.67,'seed',1)); ...
    'glm2_067',      as(ideal,'dco_glitch_fs_per_code',0.67,'dsm_dco_mode',2,'seed',7)};
end

fid = fopen(fullfile(top_dir,'output','noise_budget','glitch_meas_verify.txt'),'a');
for k = 1:size(runs,1)
    key = runs{k,1}; odir = ['nb_' key]; over = runs{k,2};
    dmp = fullfile(top_dir,'output',odir,'DBG_phi_abs_err.txt');
    if exist(dmp,'file')==2
        e_full = readmatrix(dmp);
        c = regexp(fileread(fullfile(top_dir,'output',odir,'metrics.txt')), ...
            '(?m)^\s*lock_time_us:\s*([-\d.]+)','tokens','once');
        lock_us = str2double(c{1});
    else
        fprintf('===== gmeas run %d/%d : %s =====\n', k, size(runs,1), key);
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
