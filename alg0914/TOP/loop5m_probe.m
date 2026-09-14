% loop5m_probe.m — pick locked kp1/ki1 for fc~5 MHz with best phase margin
% (loop includes the two-cycle latency z^-2; at wc=0.314 rad/sample the delay
% already costs 36 deg, so the PI zero must sit well below crossover).
% Diagnostic only.
top_dir = fileparts(mfilename('fullpath'));
addpath(fullfile(top_dir,'funcs_top'));
addpath(fullfile(top_dir,'..','funcs'));
cfg  = read_cfg_txt(fullfile(top_dir,'cfg','top_cfg.txt'));
fref = cfg.fref;  Ka = cfg.dco_abank_span/511;  G = Ka/fref;
f  = logspace(3, log10(fref/2), 4000)';
z  = exp(1i*2*pi*f/fref);
fprintf('   kp1     ki1     fc(MHz)   PM(deg)   peak(x)   peak@kHz\n');
for ki = [2 3 4 4.25 6]
    for kp = [384 448 512 576 640]
        L  = (kp + ki./(1-z.^-1)) .* G ./ (1-z.^-1) .* z.^-2;
        mag = abs(L);  ix = find(mag<1, 1);
        if isempty(ix), continue; end
        ix = min(ix+1,numel(f));
        pm  = 180 + angle(L(ix))*180/pi;
        T   = abs(1./(1+L));  [~,ip] = max(T);
        fprintf('  %5d   %6.2f    %5.2f     %5.1f     %5.1f      %.0f\n', ...
            kp, ki, f(ix)/1e6, pm, T(ip), f(ip)/1e3);
    end
end
