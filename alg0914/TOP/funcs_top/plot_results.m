function plot_results(L,M,cfg,outdir)
% plot_results — the five result figures (English labels for headless font
% safety), saved as PNG into outdir.

fcw = cfg.adpll_fcw/2^35;
fref = cfg.fref;
Tdco = 1/(fcw*fref);
N = length(L.phe_q);
tus = (0:N-1)'/fref*1e6;                     % us
state_names = {'IDLE','AFC','FLL','PLL','LOCK','UNLOCK'};

% ---- fig1: frequency acquisition -------------------------------------------
fig = figure('Visible','off','Position',[100 100 900 700]);
subplot(3,1,1);
plot(tus, L.f_dco/1e9,'b'); hold on;
yline(fcw*fref/1e9,'r--','target','LabelHorizontalAlignment','left');
ylabel('f_{DCO} (GHz)'); grid on;
title(sprintf('ADPLL closed-loop (physical 3-bank DCO): scenario %s  (FCW=%.4f, %.4f GHz)', ...
      cfg.scenario_name, fcw, fcw*fref/1e9));
draw_state_bands(L.fsm, tus);
subplot(3,1,2);
plot(tus, L.freq_ctrl_q,'b', tus, L.lpf_out,'r');
ylabel('ctrl (abank codes)'); grid on;
legend('freq\_ctrl (FLL)','lpf\_out','Location','best');
subplot(3,1,3);
stairs(tus, L.pbank,'b'); hold on;
yyaxis right; plot(tus, L.abank,'r');
ylabel('pbank / abank'); xlabel('time (us)'); grid on;
legend('pbank (AFC)','abank','Location','best');
print(fig, fullfile(outdir,'fig1_freq_acquire.png'),'-dpng','-r110');

% ---- fig2: phase transient --------------------------------------------------
fig = figure('Visible','off','Position',[100 100 900 400]);
plot(tus, L.phe_q*Tdco*1e15,'b'); hold on;
yl = ylim;
plot(tus, double(L.freq_lock)*max(abs(yl))*0.8,'g');
plot(tus, double(L.phase_lock)*max(abs(yl))*0.9,'m');
yline(200,'r:'); yline(-200,'r:');
ylabel('phe\_out (fs)'); xlabel('time (us)'); grid on;
legend('phase error','freq\_lock','phase\_lock','+-200fs spec','Location','northeast');
title(sprintf('lock time = %.1f us, steady RMS = %.1f fs', M.lock_time_us, M.phe_rms_fs));
if ~isnan(M.lock_idx) && M.lock_idx < N
    xlim([0 min(M.lock_idx/fref*1e6*2, tus(end))]);
end
print(fig, fullfile(outdir,'fig2_phase_transient.png'),'-dpng','-r110');

% ---- fig3: calibrations -----------------------------------------------------
fig = figure('Visible','off','Position',[100 100 900 600]);
subplot(3,1,1);
plot(tus, L.kdtc,'b'); hold on;
yline(M.kdtc_target,'r--','kdtc*');
ylabel('kdtc'); grid on;
title('background calibrations');
subplot(3,1,2);
plot(tus, L.dtc_code,'b', tus, L.eq*280+280,'r');
ylabel('dtc\_code / eq'); grid on;
legend('dtc\_code','280*(1+eq)','Location','best');
subplot(3,1,3);
plot(tus, L.dco_dtc_comp,'b', tus, L.ref_calib_comp*2^31,'r');
ylabel('dco\_comp / ref\_comp'); xlabel('time (us)'); grid on;
legend('dco\_dtc\_comp','ref\_calib\_comp(2^{31})','Location','best');
print(fig, fullfile(outdir,'fig3_calib.png'),'-dpng','-r110');

% ---- fig4: phase-error spectrum --------------------------------------------
fig = figure('Visible','off','Position',[100 100 900 400]);
phe_ss = L.phe_q(floor(N/2):end);
[f,Lpsd] = psd_phe(phe_ss,fref);
semilogx(f(f>1e3),Lpsd(f>1e3),'b'); hold on;
frac = fcw - floor(fcw);
xline(frac*fref,'r--',sprintf('%gx f_{ref}',frac));
ylabel('L(f) (dBc/Hz)'); xlabel('offset (Hz)'); grid on;
xlim([1e4 fref/2]);
title(sprintf('phase-error spectrum, frac-N spur at %.3f MHz: %.1f dBc', ...
      frac*fref/1e6, M.spur_dbc));
print(fig, fullfile(outdir,'fig4_spectrum.png'),'-dpng','-r110');

% ---- fig5: steady-state histogram ------------------------------------------
fig = figure('Visible','off','Position',[100 100 600 400]);
tail = floor(0.8*N):N;
histogram(L.phe_q(tail)*Tdco*1e15, 64);
ylabel('count'); xlabel('steady-state phe\_out (fs)'); grid on;
title(sprintf('steady-state phase error, RMS = %.1f fs (TDC LSB = %.0f fs)', ...
      M.phe_rms_fs, 2^-8*Tdco*1e15));
print(fig, fullfile(outdir,'fig5_eye_hist.png'),'-dpng','-r110');
close all;
end

function draw_state_bands(fsm, tus)
% shade the background by FSM state segment
cols = [0.92 0.92 0.92; 0.95 0.90 0.90; 0.90 0.95 0.90; 0.90 0.90 0.97; 0.88 0.97 0.88; 0.97 0.88 0.88];
yl = ylim;
fsm = double(fsm(:));
n = numel(fsm);
edges = [1; find(diff(fsm)~=0)+1; n+1];
for k=1:numel(edges)-1
    seg = fsm(edges(k));
    if seg<0 || seg>5, continue; end
    t0 = tus(edges(k)); t1 = tus(min(edges(k+1)-1,n));
    patch([t0; t1; t1; t0], [yl(1); yl(1); yl(2); yl(2)], cols(seg+1,:), ...
          'FaceAlpha',0.15,'EdgeColor','none');
end
end
