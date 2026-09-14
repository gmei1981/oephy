% nb_ng.m / nb_ng_b.m — no-glitch floor + glitch-amplitude scaling in the
%   NOISE-DRIVEN switching regime (total runs, ambient noise on, glitch
%   swept to 0/10/30 fs per unit code).  Companion to nb_bw_verify.m.
%   nb_ng   : tot5m_ng, tot3m_ng, tot2m_ng   (glitch=0 floor per fc)
%   nb_ng_b : tot2m_g10, tot2m_g30, tot5m_g10 (fs/code scaling, total runs)
%   Summary appended -> output/noise_budget/bw_verify.txt.  Diagnostic only.
top_dir = fileparts(mfilename('fullpath'));
addpath(fullfile(top_dir,'funcs_top'));
addpath(fullfile(top_dir,'..','funcs'));
cfg0 = read_cfg_txt(fullfile(top_dir,'cfg','top_cfg.txt'));
fref = cfg0.fref; fout = cfg0.adpll_fcw/2^35*fref; N = round(cfg0.n_cycles);
i0min = cfg0.inl_calib_start_cycle + 15000;
BW2 = struct('kp1',213.7, 'ki1',0.417);
BW3 = struct('kp1',320.3, 'ki1',0.626);
BW5 = struct('kp1',512,   'ki1',4);
if endsWith(mfilename,'_b')
  runs = { ...
    'tot2m_g10', as(BW2,'dsm_dco_mode',2,'dco_glitch_fs_per_code',10, 'seed',7); ...
    'tot2m_g30', as(BW2,'dsm_dco_mode',2,'dco_glitch_fs_per_code',30, 'seed',7); ...
    'tot5m_g10', as(BW5,'dsm_dco_mode',2,'dco_glitch_fs_per_code',10, 'seed',7)};
else
  runs = { ...
    'tot5m_ng', as(BW5,'dsm_dco_mode',2,'dco_glitch_fs_per_code',0,'seed',7); ...
    'tot3m_ng', as(BW3,'dsm_dco_mode',2,'dco_glitch_fs_per_code',0,'seed',7); ...
    'tot2m_ng', as(BW2,'dsm_dco_mode',2,'dco_glitch_fs_per_code',0,'seed',7)};
end
fid = fopen(fullfile(top_dir,'output','noise_budget','bw_verify.txt'),'a');
for k = 1:size(runs,1)
    key = runs{k,1}; odir = ['nb_' key]; over = runs{k,2};
    dmp = fullfile(top_dir,'output',odir,'DBG_phi_abs_err.txt');
    if exist(dmp,'file')==2
        e_full = readmatrix(dmp);
        c = regexp(fileread(fullfile(top_dir,'output',odir,'metrics.txt')), ...
            '(?m)^\s*lock_time_us:\s*([-\d.]+)','tokens','once');
        lock_us = str2double(c{1});
    else
        fprintf('===== ng run %d/%d : %s =====\n', k, size(runs,1), key);
        R = top_adpll('default', as(over,'outdir_name',odir));
        e_full = R.phi_abs_err;
        lock_us = (find(R.phase_lock==1,1)-1)/fref*1e6;
    end
    i0 = max(ceil(1.5*(round(lock_us*1e-6*fref)+1)), i0min);
    e = detrend(e_full(i0:N), 1);
    [fk,Lk] = psd_phe(e, fref);
    sig = sqrt(2*trapz(fk(2:end),10.^(Lk(2:end)/10)))/(2*pi*fout)*1e15;
    binw = fk(2)-fk(1); spur25 = Lk(round(25e6/binw)+1);
    fprintf('%15s : %8.1f %7.0f %11.1f %10.1f\n', key, lock_us, i0/fref*1e6, sig, spur25);
    fprintf(fid,'%s: lock_us=%.2f seg_start_us=%.0f sigma_t_fs=%.1f spur25_dBc=%.2f\n', ...
        key, lock_us, i0/fref*1e6, sig, spur25);
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
