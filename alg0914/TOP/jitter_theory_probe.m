% jitter_theory_probe.m — where does the output jitter power actually live?
% Recomputes the noise_budget analysis for cached solo runs, tabulates
% cumulative sigma_t per band, finds the dominant spectral peaks, and checks
% whether the background calibrations (kdtc/g2) wander in sympathy.
% Diagnostic only.
top_dir = fileparts(mfilename('fullpath'));
addpath(fullfile(top_dir,'funcs_top'));
addpath(fullfile(top_dir,'..','funcs'));
cfg0 = read_cfg_txt(fullfile(top_dir,'cfg','top_cfg.txt'));
fref = cfg0.fref; fout = cfg0.adpll_fcw/2^35*fref; Tdco = 1/fout;
N = round(cfg0.n_cycles); i0 = 165000;
dirs = {'nb_tdcinlq_m2','nb_glitch_m2','nb_tdcq_m2','nb_total_m2'};
fprintf('Tdco=%.2f ps  fout=%.4f GHz  (kdtc LMS mu=2^-16)\n', Tdco*1e12, fout/1e9);
for q = 1:numel(dirs)
    d = dirs{q};
    e  = readmatrix(fullfile(top_dir,'output',d,'DBG_phi_abs_err.txt'));
    kd = readmatrix(fullfile(top_dir,'output',d,'DBG_kdtc.txt'));
    g2 = readmatrix(fullfile(top_dir,'output',d,'DBG_g2.txt'));
    es = detrend(e(i0:N),1);
    [fk,Lk] = psd_phe(es,fref);
    Lin = 10.^(Lk/10); binw = fk(2)-fk(1);
    cum = sqrt(2*cumtrapz(fk,Lin))/(2*pi*fout)*1e15;
    bi = @(f) round(f/binw)+1;
    b  = @(f1,f2) sqrt(max(cum(bi(f2))^2 - cum(bi(f1))^2, 0));
    sel = bi(100e3):bi(1e6);                      % the band that carries the power
    [Lpk,ipk] = maxk(Lin(sel), 3); fpk = fk(sel(ipk));
    spot = '';
    for fq = [150e3 200e3 220e3 300e3 500e3]
        spot = [spot sprintf('  L(%gk)=%.0f', fq/1e3, Lk(bi(fq)))]; %#ok<AGROW>
    end
    kds = kd(i0:N); g2s = g2(i0:N);
    fprintf('\n%s: std(e)=%.0f fs | bands(fs): 12-100k %.0f | 100k-1M %.0f | 1M+ %.0f\n', ...
        d, std(es)*Tdco*1e15, b(12.2e3,100e3), b(100e3,1e6), b(1e6,50e6));
    fprintf('   peaks: %.0f dBc/Hz @ %.0f kHz | %.0f @ %.0f | %.0f @ %.0f |%s\n', ...
        10*log10(Lpk(1)), fpk(1)/1e3, 10*log10(Lpk(2)), fpk(2)/1e3, ...
        10*log10(Lpk(3)), fpk(3)/1e3, spot);
    fprintf('   calib wander: kdtc mean=%.2f std=%.3f | g2 mean=%.5f std=%.5f\n', ...
        mean(kds), std(kds), mean(g2s), std(g2s));
    % spectrum of the kdtc wander (normalized to its own std)
    [fk2,Lk2] = psd_phe(detrend(kds,1)-mean(kds),fref);
    [~,im] = max(Lk2(bi(100e3):bi(1e6)));
    fprintf('   kdtc-wander dominant bin ~%.0f kHz (band 100k-1M)\n', ...
        fk2(bi(100e3)+im-1)/1e3);
end
