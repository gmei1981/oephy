% noise_budget.m — output phase-noise decomposition + frequency/PN curves.
%
%   Run (from alg0908):   matlab -batch "addpath('TOP'); noise_budget"
%
%   Method (linear superposition around the locked operating point): the
%   closed loop is run once per noise source with every OTHER source
%   idealized (cfg overrides understood by top_adpll):
%     total   : cfg as-is  (DCO -120 dBc/Hz@1MHz, 10 dB/dec, floor -150;
%               TDC 1/256-cyc quantization + INL; DTC spec INL/DNL + 159 fs
%               PN floor; DSM leak; fbank SDM; code-switch glitch)
%     dco     : DCO colored PN only
%     tdc     : TDC quantization, loop otherwise STATIC (eq=0, no noise) —
%               diagnostic only: without DSM dither the phase sits on one
%               code and quantization noise vanishes (~0)
%     dtc     : DTC PN-floor thermal jitter only (159 fs white edge jitter)
%     dsm     : DSM leak via the spec-nonlinearity DTC, TDC IDEAL —
%               diagnostic only: without detector dither the kdtc/g2
%               correlators limit-cycle (slow deterministic wobble, NOT
%               representative; excluded from the budget)
%     dsmq    : DSM leak + TDC quantization (both well-dithered, DTC INL on)
%     tdcq    : TDC quantization under DSM dither with a LINEAR DTC
%               (INL off)  ->  clean TDC-quantization entry
%     tdcinlq : dsmq + TDC INL (1 LSB) on  ->  TDC INL = power(tdcinlq)-power(dsmq)
%     glitch  : fine-bank code-switch glitch only (100 fs/unit-code)
%     --- 2026-09-13 additions ------------------------------------------------
%     refjit  : reference-clock jitter only (50 fs RMS white, ASSUMED — no
%               spec number exists; direct solo run, ref noise is tracked by
%               the loop so it lands low-pass at the output)
%     tdcnq   : tdcq + TDC thermal noise 0.1 LSB (1 LSB = 1/256 DCO cycle =
%               487 fs  ->  ~49 fs RMS, ASSUMED)  ->  TDC thermal =
%               power(tdcnq)-power(tdcq)
%     glitch10/30/300 : glitch sweep around the 100 fs/code assumption
%               (the glitch entry dominates the budget, so the conclusion
%               must survive this sweep)
%     --- 2026-09-14 additions (glitch re-eval on the REAL 3-bit fbank) --------
%     *_m2     : same runs with dsm_dco_mode=2 (8-cell fbank, unit step =
%               1/8 abank LSB).  The 1-bit mode=0 glitch entry (1107 fs)
%               turned out to be an abank-integer-boundary limit-cycle
%               artifact of the temporary 1-bit architecture; mode=2 has no
%               such boundary amplification (unit toggles are 1 code, not 8).
%     total_m2 : all sources, mode=2 -> superposition check with the real
%               fbank (also refreshes the mode-2 closed-loop metrics).
%     glitch_m2_s1/s2/s3 : seed spread at 100 fs/code (orbit statistics:
%               the mode=0 result was worst-orbit, so quote a spread, not
%               one number).
%
%   Runs already dumped under TOP/output/<name>/ (DBG_phi_abs_err.txt +
%   metrics.txt present) are reused from disk instead of re-simulated —
%   delete the directory to force a re-run.
%
%   Output phase error e(i) = phi_abs(i) - i*FCW (DCO cycles) over the
%   segment that starts AFTER all calibrations settled (>= 1.5x lock time
%   and >= inl_calib_start_cycle + 15k cycles), linear-detrended;
%   L(f) = S_phi/2 via psd_phe (Hann Welch, RBW 12.2 kHz).
%
%   Outputs -> TOP/output/noise_budget/:
%     fig_nb1_freq_transient.png   frequency lock curve (total run)
%     fig_nb2_pn_decomp.png        L(f) decomposition, total + contributors
%     noise_budget.txt             integrated jitter / spur summary

top_dir = fileparts(mfilename('fullpath'));
addpath(fullfile(top_dir,'funcs_top'));
addpath(fullfile(top_dir,'..','funcs'));

cfg0   = read_cfg_txt(fullfile(top_dir,'cfg','top_cfg.txt'));
fref   = cfg0.fref;
fcw    = cfg0.adpll_fcw/2^35;
fout   = fcw*fref;
N      = round(cfg0.n_cycles);
i0min  = cfg0.inl_calib_start_cycle + 15000;    % after the g2 correlator starts
outdir = fullfile(top_dir,'output','noise_budget');
if ~exist(outdir,'dir'), mkdir(outdir); end
fid = fopen(fullfile(outdir,'noise_budget.txt'),'w');

% ---- solo-run baseline: everything ideal except the source under test ------
ideal = struct( ...
    'tdc_ideal',1, ...                    % no 1/256 quantization / INL
    'dsm_fb_ideal',1, ...                 % exact fractional divide, eq = 0
    'tdc_inl_en',0, ...
    'dtc_inl_lsb',0, 'dtc_dnl_lsb',0, 'dtc_pn_floor_dbc',-300, ...
    'dco_pn_l1m_dbc',-300, 'dco_pn_floor_dbc',-300, 'dco_pn_rms_fs',0, ...
    'dco_pn_spec_f_hz','', 'dco_pn_spec_dbc','', ...   % piecewise table off
    'dco_glitch_fs_per_code',0, 'ref_jitter_fs',0);
dsm_real = struct('dsm_fb_ideal',0, 'dtc_inl_lsb',2, 'dtc_dnl_lsb',1);
dsmq_ov  = as(merge(ideal, dsm_real), 'tdc_ideal',0);        % + TDC quant dither
% DCO-PN solo run: inherit the piecewise measured spec from the cfg (whatever
% it currently says — single source of truth, no hard-coded numbers here)
dco_real = struct('dco_pn_spec_f_hz',cfg0.dco_pn_spec_f_hz, ...
                  'dco_pn_spec_dbc',cfg0.dco_pn_spec_dbc);

runs = { ...
  'total',   'Total (all sources)',                           'default', struct(); ...
  'dco',     'DCO PN (cfg piecewise spec)',                   'nb_dco', ...
              merge(ideal, dco_real); ...
  'tdc',     'TDC quant., undithered (diagnostic ~0)',         'nb_tdc', ...
              as(ideal); ...
  'dtc',     'DTC thermal (159 fs)',                           'nb_dtc', ...
              as(ideal,'dtc_pn_floor_dbc',-160); ...
  'dsm',     'DSM leak, TDC ideal (diagnostic: LMS limit cycle)', 'nb_dsm', ...
              merge(ideal, dsm_real); ...
  'dsmq',    'DSM leak + TDC quant. (dithered)',               'nb_dsmq', ...
              as(dsmq_ov, 'outdir_name','nb_dsmq'); ...
  'tdcq',    'TDC quant. (DSM-dithered, linear DTC)',          'nb_tdcq', ...
              as(as(ideal,'dsm_fb_ideal',0), 'tdc_ideal',0, 'outdir_name','nb_tdcq'); ...
  'tdcinlq', 'dsmq + TDC INL 1 LSB',                           'nb_tdcinlq', ...
              as(dsmq_ov, 'tdc_inl_en',1, 'outdir_name','nb_tdcinlq'); ...
  'glitch',  'fine-bank switching glitch (100 fs/code)',       'nb_glitch', ...
              as(ideal, 'dco_glitch_fs_per_code',100, 'outdir_name','nb_glitch'); ...
  'refjit',  'Reference jitter (50 fs RMS, assumed)',          'nb_refjit', ...
              as(ideal, 'ref_jitter_fs',50, 'outdir_name','nb_refjit'); ...
  'tdcnq',   'TDC quant + thermal 0.1 LSB (~49 fs)',           'nb_tdcnq', ...
              as(as(ideal,'dsm_fb_ideal',0), 'tdc_ideal',0, 'tdc_noise_lsb',0.1, ...
                 'outdir_name','nb_tdcnq'); ...
  'glitch10',  'glitch sweep 10 fs/code',   'nb_glitch10', ...
              as(ideal, 'dco_glitch_fs_per_code',10,  'outdir_name','nb_glitch10'); ...
  'glitch30',  'glitch sweep 30 fs/code',   'nb_glitch30', ...
              as(ideal, 'dco_glitch_fs_per_code',30,  'outdir_name','nb_glitch30'); ...
  'glitch300', 'glitch sweep 300 fs/code',  'nb_glitch300', ...
              as(ideal, 'dco_glitch_fs_per_code',300, 'outdir_name','nb_glitch300'); ...
  % --- 2026-09-14: glitch re-eval on the real 3-bit fbank (dsm_dco_mode=2) ---
  'total_m2',    'Total, 3-bit fbank (mode=2)',        'nb_total_m2', ...
              struct('dsm_dco_mode',2, 'outdir_name','nb_total_m2'); ...
  'glitch_m2',   'glitch mode=2 (100 fs/code)',        'nb_glitch_m2', ...
              as(ideal, 'dco_glitch_fs_per_code',100, 'dsm_dco_mode',2, ...
                 'outdir_name','nb_glitch_m2'); ...
  'glitch_m2_10',  'glitch m2 sweep 10 fs/code',  'nb_glitch_m2_10', ...
              as(ideal, 'dco_glitch_fs_per_code',10,  'dsm_dco_mode',2, ...
                 'outdir_name','nb_glitch_m2_10'); ...
  'glitch_m2_30',  'glitch m2 sweep 30 fs/code',  'nb_glitch_m2_30', ...
              as(ideal, 'dco_glitch_fs_per_code',30,  'dsm_dco_mode',2, ...
                 'outdir_name','nb_glitch_m2_30'); ...
  'glitch_m2_300', 'glitch m2 sweep 300 fs/code', 'nb_glitch_m2_300', ...
              as(ideal, 'dco_glitch_fs_per_code',300, 'dsm_dco_mode',2, ...
                 'outdir_name','nb_glitch_m2_300'); ...
  'glitch_m2_s1', 'glitch m2 seed spread (seed 1)', 'nb_glitch_m2_s1', ...
              as(ideal, 'dco_glitch_fs_per_code',100, 'dsm_dco_mode',2, 'seed',1, ...
                 'outdir_name','nb_glitch_m2_s1'); ...
  'glitch_m2_s2', 'glitch m2 seed spread (seed 2)', 'nb_glitch_m2_s2', ...
              as(ideal, 'dco_glitch_fs_per_code',100, 'dsm_dco_mode',2, 'seed',2, ...
                 'outdir_name','nb_glitch_m2_s2'); ...
  'glitch_m2_s3', 'glitch m2 seed spread (seed 3)', 'nb_glitch_m2_s3', ...
              as(ideal, 'dco_glitch_fs_per_code',100, 'dsm_dco_mode',2, 'seed',3, ...
                 'outdir_name','nb_glitch_m2_s3'); ...
  % TDC-INL / DSM-leak entries re-measured under mode=2 (fbank ripple differs,
  % and these detector-domain leaks ride on the ripple: tdcinlq_m2 = dsmq_m2 +
  % TDC INL, dsmq_m2 = DSM leak + TDC quant under the real 3-bit fbank)
  'dsmq_m2',    'DSM leak + TDC quant., mode=2',   'nb_dsmq_m2', ...
              as(dsmq_ov, 'dsm_dco_mode',2, 'outdir_name','nb_dsmq_m2'); ...
  'tdcq_m2',    'TDC quant. (dithered), mode=2',   'nb_tdcq_m2', ...
              as(as(ideal,'dsm_fb_ideal',0), 'tdc_ideal',0, 'dsm_dco_mode',2, ...
                 'outdir_name','nb_tdcq_m2'); ...
  'tdcinlq_m2', 'dsmq_m2 + TDC INL 1 LSB',         'nb_tdcinlq_m2', ...
              as(dsmq_ov, 'tdc_inl_en',1, 'dsm_dco_mode',2, ...
                 'outdir_name','nb_tdcinlq_m2')};

n   = size(runs,1);
PSD = cell(n,1);  fres = [];
sig_fs = nan(n,1); lock_us = nan(n,1); spur25 = nan(n,1); spur50 = nan(n,1);
e_full = cell(n,1); freq_tot = [];

for k = 1:n
    [key,~,odir,over] = runs{k,:};
    dmp = fullfile(top_dir,'output',odir,'DBG_phi_abs_err.txt');
    mts = fullfile(top_dir,'output',odir,'metrics.txt');
    if exist(dmp,'file')==2 && exist(mts,'file')==2
        fprintf('\n===== noise_budget %d/%d : %s (cached from output/%s) =====\n', ...
            k, n, key, odir);
        e_full{k} = readmatrix(dmp);
        lock_us(k) = read_lock_us(mts);
        if strcmp(key,'total')
            f_hz = readmatrix(fullfile(top_dir,'output',odir,'DBG_dco_freq_hz.txt'));
            freq_tot = f_hz(1:N);
        end
    else
        fprintf('\n===== noise_budget run %d/%d : %s =====\n', k, n, key);
        Lk_run = top_adpll('default', over);
        e_full{k} = Lk_run.phi_abs_err;
        lock_us(k) = (find(Lk_run.phase_lock==1,1)-1)/fref*1e6;   % ~first assert
        if strcmp(key,'total'), freq_tot = Lk_run.f_dco; end
    end

    % ---- settled segment of the output phase error -------------------------
    lock_idx = max(round(lock_us(k)*1e-6*fref)+1, 2);
    i0 = max(ceil(1.5*lock_idx), i0min);
    e = detrend(e_full{k}(i0:N), 1);           % remove mean + freq-offset ramp

    [fk,Lk] = psd_phe(e,fref);
    PSD{k} = {fk,Lk};  fres = fk;
    Lin = 10.^(Lk/10);
    sig_fs(k)  = sqrt(2*trapz(fk(2:end),Lin(2:end)))/(2*pi*fout)*1e15;  % RBW..fref/2
    binw = fk(2)-fk(1);
    spur25(k)  = Lk(round(25e6/binw)+1);                 % exact DFT bins
    spur50(k)  = Lk(round(50e6/binw)+1);
    spot = '';
    for fq = [50e3 200e3 1e6 5e6]
        spot = [spot sprintf('  L(%gk)=%.0f', fq/1e3, Lk(round(fq/binw)+1))]; %#ok<AGROW>
    end
    fprintf('   locked @ %.1f us, seg from %.0f us | sigma_t = %.1f fs | spur25 %+.1f dBc%s\n', ...
        lock_us(k), i0/fref*1e6, sig_fs(k), spur25(k), spot);
    fprintf(fid,'%s: lock_us=%.2f seg_start_us=%.0f sigma_t_fs=%.1f spur25_dBc=%.2f spur50_dBc=%.2f%s\n', ...
        key, lock_us(k), i0/fref*1e6, sig_fs(k), spur25(k), spur50(k), spot);
end

% ---- budget entries by run key (order-independent lookup) -------------------
% diagnostics 'tdc'(3) & 'dsm' are excluded;  tdcnq/refjit/glitch-sweep are
% additional sources outside the cached six-entry budget.
ik = @(k) find(strcmp(runs(:,1),k));                    % index of run key k
sig_tdcq  = sig_fs(ik('tdcq'));                        % TDC quant (dithered)
sig_tdcinl= sqrt(max(sig_fs(ik('tdcinlq'))^2 - sig_fs(ik('dsmq'))^2, 0)); % TDC INL = tdcinlq-dsmq
sig_dsml  = sqrt(max(sig_fs(ik('dsmq'))^2 - sig_fs(ik('tdcq'))^2, 0));    % DSM leak = dsmq-tdcq
sig_refjit= sig_fs(ik('refjit'));                      % solo run (direct)
sig_tdcn  = sqrt(max(sig_fs(ik('tdcnq'))^2 - sig_fs(ik('tdcq'))^2, 0));   % TDC thermal = tdcnq-tdcq
contrib = [sig_fs(ik('dco')) sig_tdcq sig_tdcinl sig_fs(ik('dtc')) sig_dsml sig_fs(ik('glitch'))];
fprintf(fid,'budget_fs: DCO=%.1f TDCquant=%.1f TDCinl=%.1f DTCthermal=%.1f DSMleak=%.1f glitch=%.1f\n', contrib);
fprintf(fid,'budget_add_fs: REFjitter(50fs,assumed)=%.1f TDCthermal(0.1LSB,assumed)=%.1f\n', ...
    sig_refjit, sig_tdcn);
fprintf(fid,'glitch_sweep_fs_per_code: 10=%.1f 30=%.1f 100=%.1f 300=%.1f (sigma_t fs)\n', ...
    sig_fs(ik('glitch10')), sig_fs(ik('glitch30')), sig_fs(ik('glitch')), sig_fs(ik('glitch300')));
fprintf(fid,'superposition: RSS(contributors) = %.1f fs vs total %.1f fs\n', ...
    sqrt(sum(contrib.^2)), sig_fs(ik('total')));

% ---- mode=2 (real 3-bit fbank) glitch re-evaluation ---------------------------
% The mode=0 glitch entry is a 1-bit abank-boundary limit-cycle artifact; the
% real-architecture budget swaps the glitch entry for the mode=2 solo run and
% re-measures the detector-domain entries (TDC quant / TDC INL / DSM leak)
% under mode=2, since their leakage rides on the fbank ripple.  DCO PN and DTC
% thermal entries are plant/edge properties, fbank-mode-insensitive -> reuse.
sig_gm2 = sig_fs(ik('glitch_m2'));
sig_tdcq_m2  = sig_fs(ik('tdcq_m2'));
sig_tdcinl_m2= sqrt(max(sig_fs(ik('tdcinlq_m2'))^2 - sig_fs(ik('dsmq_m2'))^2, 0));
sig_dsml_m2  = sqrt(max(sig_fs(ik('dsmq_m2'))^2 - sig_tdcq_m2^2, 0));
contrib_m2 = [sig_fs(ik('dco')) sig_tdcq_m2 sig_tdcinl_m2 sig_fs(ik('dtc')) sig_dsml_m2 sig_gm2];
fprintf(fid,'budget_m2_fs (real 3-bit fbank): DCO=%.1f TDCquant=%.1f TDCinl=%.1f DTCthermal=%.1f DSMleak=%.1f glitch_m2=%.1f\n', ...
    contrib_m2);
fprintf(fid,'glitch_m2_sweep_fs_per_code: 10=%.1f 30=%.1f 100=%.1f 300=%.1f (sigma_t fs)\n', ...
    sig_fs(ik('glitch_m2_10')), sig_fs(ik('glitch_m2_30')), sig_gm2, sig_fs(ik('glitch_m2_300')));
fprintf(fid,'glitch_m2_seed_spread_fs: seed7=%.1f seed1=%.1f seed2=%.1f seed3=%.1f (100 fs/code)\n', ...
    sig_gm2, sig_fs(ik('glitch_m2_s1')), sig_fs(ik('glitch_m2_s2')), sig_fs(ik('glitch_m2_s3')));
fprintf(fid,'superposition_m2: RSS(contributors, glitch_m2) = %.1f fs vs total_m2 %.1f fs\n', ...
    sqrt(sum(contrib_m2.^2)), sig_fs(ik('total_m2')));

% ======================== fig_nb1: frequency transient =======================
tus = (1:N)'/fref*1e6;
fig1 = figure('Visible','off','Position',[100 100 900 650]);
subplot(2,1,1);                                % full run, log time
semilogx(tus, freq_tot/1e9, 'b'); hold on;
yline(fout/1e9,'k--',sprintf('%.4f GHz',fout/1e9));
xline(find(readmatrix(fullfile(top_dir,'output','default','DBG_afc_finish.txt'))==1,1)/fref*1e6, ...
    ':','AFC');
xline(round(lock_us(1)*1e-6*fref)/fref*1e6, ':', 'lock');
grid on; xlim([1 2621]); xlabel('time (\mus, log)'); ylabel('f_{DCO} (GHz)');
title(sprintf('Frequency lock transient — FCW=%.2f (%.4f GHz), f_{ref}=100 MHz', fcw, fout/1e9));
subplot(2,1,2);                                % early transient, linear time
plot(tus, freq_tot/1e9, 'b'); hold on;
yline(fout/1e9,'k--');
grid on; xlim([0 400]); xlabel('time (\mus)'); ylabel('f_{DCO} (GHz)');
title('AFC sub-band steps -> FLL -> PLL fine lock (linear time, 0-400 \mus)');
print(fig1,'-dpng','-r150',fullfile(outdir,'fig_nb1_freq_transient.png'));

% ======================== fig_nb2: PN decomposition ==========================
fig2 = figure('Visible','off','Position',[100 100 950 700]);
sel  = cellfun(ik, {'total','dco','tdcq','dtc','glitch','refjit'}, ...
               'UniformOutput', true);           % solid curves
cols = {[0 0 0],'r','c','g','b',[1 0.5 0]};      % total,dco,tdcq,dtc,glitch,refjit
hold on;
for q = 1:numel(sel)
    c = PSD{sel(q)};
    semilogx(c{1}(2:end), c{2}(2:end), '-', 'Color', cols{q}, ...
             'LineWidth', (q==1)*0.5+1.0);
end
% derived contributors (power differences between dithered pairs)
pd = @(a,b) 10*log10(max(10.^(PSD{a}{2}/10) - 10.^(PSD{b}{2}/10), 1e-20));
L_dsml  = pd(ik('dsmq'),ik('tdcq'));    semilogx(fres(2:end), L_dsml(2:end),  'm--', 'LineWidth', 1.0);
L_tdcinl= pd(ik('tdcinlq'),ik('dsmq')); semilogx(fres(2:end), L_tdcinl(2:end),'c--', 'LineWidth', 1.0);
L_tdcn  = pd(ik('tdcnq'),ik('tdcq'));   semilogx(fres(2:end), L_tdcn(2:end),  '--','Color',[0.6 0.4 0], 'LineWidth', 1.0);
% power sum of contributors vs the total (superposition check)
base = cellfun(ik, {'dco','dtc','dsmq','tdcq','glitch'});   % covers the six cached contributors once
Pc = cellfun(@(c) 10.^(c{2}/10), PSD(base), 'UniformOutput', false);
Lsum_db = 10*log10(sum(cat(2,Pc{:}),2));
semilogx(fres(2:end), Lsum_db(2:end), 'k--', 'LineWidth', 0.8);
grid on; xlim([1.2e4 fref/2]); ylim([-190 -60]);
xlabel('offset frequency (Hz)'); ylabel('L(f) (dBc/Hz)');
ttl1 = sprintf('Output phase noise decomposition, locked state (Hann Welch, RBW %.1f kHz)', ...
    fref/8192/1e3);
ttl2 = sprintf(['integrated \\sigma_t (%g kHz..%g MHz): total %.0f fs | DCO %.0f | TDCq %.0f' ...
    ' | TDCinl %.0f | DTC %.0f | DSM %.0f | glitch %.0f | REFj %.0f | TDCn %.0f fs'], ...
    fres(2)/1e3, fref/2/1e6, sig_fs(ik('total')), sig_fs(ik('dco')), sig_tdcq, ...
    sig_tdcinl, sig_fs(ik('dtc')), sig_dsml, sig_fs(ik('glitch')), sig_refjit, sig_tdcn);
title({ttl1, ttl2});
leg = [runs(sel,2); {'TDC INL (tdcinlq-dsmq)'}; {'DSM leak (dsmq-tdcq)'}; ...
       {'TDC thermal (tdcnq-tdcq)'}; {'\Sigma contributors (power sum)'}];
legend(leg, 'Location','southwest','FontSize',8);
print(fig2,'-dpng','-r150',fullfile(outdir,'fig_nb2_pn_decomp.png'));

% ======================== fig_nb3: glitch-parameter sweep =====================
fig3 = figure('Visible','off','Position',[100 100 950 650]);
gk   = {'glitch10','glitch30','glitch','glitch300'};
gm2k = {'glitch_m2_10','glitch_m2_30','glitch_m2','glitch_m2_300'};
cols3= {[0 0.6 0],'b','r',[0.5 0 0.5]};
hold on;
for q = 1:4                                   % mode=0 (temporary 1-bit fbank)
    c = PSD{ik(gk{q})};
    semilogx(c{1}(2:end), c{2}(2:end), '-', 'Color', cols3{q}, 'LineWidth', 1.0);
end
for q = 1:4                                   % mode=2 (real 3-bit fbank)
    c = PSD{ik(gm2k{q})};
    semilogx(c{1}(2:end), c{2}(2:end), '--', 'Color', cols3{q}, 'LineWidth', 1.2);
end
grid on; xlim([1.2e4 fref/2]); ylim([-190 -60]);
xlabel('offset frequency (Hz)'); ylabel('L(f) (dBc/Hz)');
title({sprintf(['Fine-bank glitch sweep — solid: mode=0 (1-bit fbank) \\sigma_t = %.0f / %.0f / %.0f / %.0f fs' ...
    ' @ 10/30/100/300 fs/code'], ...
    sig_fs(ik('glitch10')), sig_fs(ik('glitch30')), sig_fs(ik('glitch')), sig_fs(ik('glitch300'))), ...
    sprintf(['dashed: mode=2 (real 3-bit fbank) \\sigma_t = %.0f / %.0f / %.0f / %.0f fs' ...
    ' | seed spread @100: %.0f / %.0f / %.0f / %.0f fs'], ...
    sig_fs(ik('glitch_m2_10')), sig_fs(ik('glitch_m2_30')), sig_gm2, sig_fs(ik('glitch_m2_300')), ...
    sig_gm2, sig_fs(ik('glitch_m2_s1')), sig_fs(ik('glitch_m2_s2')), sig_fs(ik('glitch_m2_s3')))});
legend({'10 fs/code m0','30 fs/code m0','100 fs/code m0','300 fs/code m0', ...
        '10 fs/code m2','30 fs/code m2','100 fs/code m2','300 fs/code m2'}, ...
    'Location','southwest','FontSize',8);
print(fig3,'-dpng','-r150',fullfile(outdir,'fig_nb3_glitch_sweep.png'));

% ---- summary ----------------------------------------------------------------
fprintf(fid,'\nRBW = %.1f kHz (nfft 8192 @ 100 MHz); integration RBW..%g MHz\n', ...
    fref/8192/1e3, fref/2/1e6);
fclose(fid);
fprintf('\nnoise_budget done -> %s\n', outdir);
fprintf('  sigma_t (fs): total %.0f | DCO %.0f | TDCq %.0f | TDCinl %.0f | DTC %.0f | DSM %.0f | glitch %.0f\n', ...
    sig_fs(ik('total')), contrib);
fprintf('  additions (fs): REFjitter(50fs)=%.0f TDCthermal(0.1LSB)=%.0f | glitch sweep 10/30/100/300: %.0f/%.0f/%.0f/%.0f\n', ...
    sig_refjit, sig_tdcn, sig_fs(ik('glitch10')), sig_fs(ik('glitch30')), ...
    sig_fs(ik('glitch')), sig_fs(ik('glitch300')));
fprintf('  superposition: RSS(contributors) = %.1f fs vs total %.1f fs\n', ...
    sqrt(sum(contrib.^2)), sig_fs(ik('total')));
fprintf('  mode=2 (real 3-bit fbank): total %.0f fs | glitch_m2 %.0f (sweep 10/30/100/300: %.0f/%.0f/%.0f/%.0f, seeds 7/1/2/3: %.0f/%.0f/%.0f/%.0f)\n', ...
    sig_fs(ik('total_m2')), sig_gm2, ...
    sig_fs(ik('glitch_m2_10')), sig_fs(ik('glitch_m2_30')), sig_gm2, sig_fs(ik('glitch_m2_300')), ...
    sig_gm2, sig_fs(ik('glitch_m2_s1')), sig_fs(ik('glitch_m2_s2')), sig_fs(ik('glitch_m2_s3')));
fprintf('  superposition_m2: RSS = %.1f fs vs total_m2 %.1f fs\n', ...
    sqrt(sum(contrib_m2.^2)), sig_fs(ik('total_m2')));

% ================= helpers ====================================================
function s = as(s,varargin)          % struct override helper
for q = 1:2:numel(varargin), s.(varargin{q}) = varargin{q+1}; end
end

function s = merge(a,b)              % merge struct b's fields into a
s = a;
f = fieldnames(b);
for q = 1:numel(f), s.(f{q}) = b.(f{q}); end
end

function lus = read_lock_us(mts)     % lock_time_us from a metrics.txt
txt = fileread(mts); lus = NaN;      % (?m)^ anchor: skip fll_lock_time_us
c = regexp(txt,'(?m)^\s*lock_time_us:\s*([-\d.]+)','tokens','once');
if ~isempty(c), lus = str2double(c{1}); end
end
