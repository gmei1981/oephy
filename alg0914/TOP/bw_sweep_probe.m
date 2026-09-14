% bw_sweep_probe.m — analytic locked-loop bandwidth sweep (2026-09-14).
%   For each target crossover fc, pick (kp1,ki1) with best phase margin
%   (ki kept on the 2^-10 lpf.m quantization grid), then predict the
%   LINEAR-source output jitter:
%     DCO   : piecewise PN spec (cfg table) x |1/(1+L)|^2, exact transfer
%     whites: TDC-quant / DSM-leak / DTC-thermal / REF-jitter measured at
%             4.84 MHz (noise_budget.txt) scaled by sqrt(ENBW ratio),
%             ENBW = int |L/(1+L)|^2 df  (detector->output is ~low-pass)
%   Glitch chatter is orbit dynamics, NOT analytic (8x fs/code at the old
%   250 kHz PM2.7 loop, 14x at 4.84 MHz PM62) -> closed-loop runs verify.
%   Validation: predicted DCO sigma at the current 4.84 MHz loop vs the
%   measured nb_dco solo run (127.9 fs) must agree (~1 dB).
% Diagnostic only.
top_dir = fileparts(mfilename('fullpath'));
addpath(fullfile(top_dir,'funcs_top'));
addpath(fullfile(top_dir,'..','funcs'));
cfg = read_cfg_txt(fullfile(top_dir,'cfg','top_cfg.txt'));
fref = cfg.fref; fout = cfg.adpll_fcw/2^35*fref;
Ka = cfg.dco_abank_span/511; G = Ka/fref;

% free-running DCO PN from the cfg piecewise table (log-log, end-slope extrap)
ftb = str2num(cfg.dco_pn_spec_f_hz);  ltb = str2num(cfg.dco_pn_spec_dbc);
f  = logspace(log10(12.2e3), log10(fref/2), 20000)';
Lf = interp1(log10(ftb(:)), ltb(:), log10(f), 'linear', 'extrap');
Llin = 10.^(Lf/10);                       % linear dBc/Hz, one-sided L=S_phi/2

Lfun = @(kp,ki) (kp + ki./(1-exp(-1i*2*pi*f/fref))) .* G ./ (1-exp(-1i*2*pi*f/fref)) ...
                 .* exp(-2i*2*pi*f/fref);

% measured mode-2 solo entries at the current 4.84 MHz / PM62 loop (fs)
w_meas = [148.8 143.2 79.6 25.0];         % TDCq, DSMleak, DTCth, REFj
[L0] = Lfun(cfg.kp1, cfg.ki1);
Tdet0 = abs(L0./(1+L0)); enbw0 = trapz(f, Tdet0.^2);
Ter0 = abs(1./(1+L0));
sdc0 = sqrt(2*trapz(f, Llin.*Ter0.^2))/(2*pi*fout)*1e15;
fprintf('validation @ kp1=%g ki1=%g: DCO predicted %.0f fs vs measured 127.9 fs | ENBW %.2f MHz\n\n', ...
    cfg.kp1, cfg.ki1, sdc0, enbw0/1e6);

fprintf(' fc_t(MHz)  kp1    ki1     fc_ac   PM   Tpk(x) |  DCO  TDCq  DSMl  DTCt  REFj | RSSlin | glitch cap @14x/8x (fs/code)\n');
for fc_t = [0.5 1 1.5 2 3 4.84]*1e6
    best = [];
    for r = [1/512 1/256 1/128 1/64 1/32]        % PI zero ratio ki/kp
        zc = exp(-1i*2*pi*fc_t/fref);
        kp = abs(1-zc) / (G * abs(1 + r/(1-zc)));% |L(fc_t)| = 1 exactly
        ki = round(kp*r*1024)/1024;               % lpf.m 2^-10 grid
        L = Lfun(kp,ki); mag = abs(L);
        ix = find(mag < 1, 1); ix = min(ix+1, numel(f));
        pm = 180 + angle(L(ix))*180/pi;
        T = abs(1./(1+L)); [~,ip] = max(T);
        if isempty(best) || pm > best.pm
            best = struct('kp',kp,'ki',ki,'fc',f(ix),'pm',pm,'tpk',T(ip),'L',L);
        end
    end
    Tdet = abs(best.L./(1+best.L)); enbw = trapz(f, Tdet.^2);
    Ter = abs(1./(1+best.L));
    sdc = sqrt(2*trapz(f, Llin.*Ter.^2))/(2*pi*fout)*1e15;
    w = w_meas * sqrt(enbw/enbw0);
    rss = sqrt(sdc^2 + sum(w.^2));
    fprintf('   %4.2f   %6.1f %6.3f  %5.2fM  %4.1f  %5.2f  | %5.0f %5.0f %5.0f %5.0f %5.0f | %6.0f |  %4.1f / %4.1f\n', ...
        fc_t/1e6, best.kp, best.ki, best.fc/1e6, best.pm, best.tpk, ...
        sdc, w(1), w(2), w(3), w(4), rss, 100/14, 100/8);
end
fprintf('\n(glitch cap = fs/code allowed for a 100 fs glitch contribution at the\n');
fprintf(' measured chatter factor; the factor itself must be re-measured per fc.)\n');
