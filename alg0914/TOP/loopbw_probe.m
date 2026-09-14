% loopbw_probe.m — locked-loop bandwidth from actual parameters, verified
% against the cached DCO-PN solo run (nb_dco).  Diagnostic only.
%
% Loop (locked): phe(k+1) = phe(k) + G*lpf(k),  G = Ka/fref  [cyc/LSB/cyc]
%                lpf(k)   = (kp + ki/(1-z^-1)) * phe(k-1)
% => L(z) = z^-2 * (kp + ki/(1-z^-1)) * G / (1-z^-1)
% lpf.m semantics: locked (phase_lock=1) uses kp1/ki1; acquisition uses kp2.
top_dir = fileparts(mfilename('fullpath'));
addpath(fullfile(top_dir,'funcs_top'));
addpath(fullfile(top_dir,'..','funcs'));
cfg  = read_cfg_txt(fullfile(top_dir,'cfg','top_cfg.txt'));
fref = cfg.fref;  fout = cfg.adpll_fcw/2^35*fref;
Ka   = cfg.dco_abank_span/511;  G = Ka/fref;
fprintf('G=Ka/fref=%.4e cyc/LSB/cyc | locked kp1=%.4f ki1=%.6f | acq kp2=%g\n', ...
    G, cfg.kp1, cfg.ki1, cfg.kp2);

f  = logspace(3, log10(fref/2), 2000)';
w  = 2*pi*f/fref;  z = exp(1i*w);
Lk = (cfg.kp1 + cfg.ki1./(1-z.^-1)) .* G ./ (1-z.^-1) .* z.^-2;
La = (cfg.kp2 + cfg.ki2./(1-z.^-1)) .* G ./ (1-z.^-1) .* z.^-2;
xl = find(abs(Lk)<1, 1);  xa = find(abs(La)<1, 1);
fprintf('unity-gain crossover: locked = %.0f kHz | acquisition(kp2) = %.0f kHz\n', ...
    f(min(xl+1,numel(f)))/1e3, f(min(xa+1,numel(f)))/1e3);
ph = angle(Lk(min(xl+1,numel(f))))*180/pi;
fprintf('locked phase margin at crossover = %.1f deg | error-transfer peak = %.1f x (+%.0f dB) @ %.0f kHz\n', ...
    180+ph, max(abs(1./(1+Lk))), 20*log10(max(abs(1./(1+Lk)))), ...
    f(find(abs(1./(1+Lk))==max(abs(1./(1+Lk))),1))/1e3);

% ---- verify against the DCO-PN solo run --------------------------------------
e  = readmatrix(fullfile(top_dir,'output','nb_dco','DBG_phi_abs_err.txt'));
[fk,Lmeas] = psd_phe(detrend(e(165000:end),1), fref);
bi = @(fq) round(fq/(fk(2)-fk(1)))+1;
fprintf('\n  f(kHz)   L_free(model)  T_err(dB)   predicted   measured(nb_dco)\n');
for fq = [50e3 100e3 200e3 250e3 500e3 1e6 5e6 10e6]
    Lfree = -120 + 10*log10(1e6/fq);                 % plant PN spec (10 dB/dec)
    [~,ix] = min(abs(f-fq));  T = abs(1/(1+Lk(ix)));
    fprintf('  %5.0f      %6.1f       %+6.1f      %6.1f        %6.1f\n', ...
        fq/1e3, Lfree, 20*log10(T), Lfree+20*log10(T), Lmeas(bi(fq)));
end
fprintf('\nDCO contribution to output sigma_t (12.2k..50M integral) = 325 fs (cached)\n');
