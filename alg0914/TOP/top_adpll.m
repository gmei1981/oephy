function L = top_adpll(scenario,cfg_over)
% top_adpll — closed-loop ADPLL algorithm simulation (top level).
%
%   Wires the golden fixed-point models from ../funcs (pfd, lpf, fll,
%   lock_detect, calib_kdtc, calib_ref_double, calib_dco_duty, dtc) into one
%   per-reference-cycle loop, together with behavioral plant models and the
%   top FSM IDLE->AFC->FLL->PLL->LOCK (UNLOCK->FLL).
%
%   DCO is modeled with the ACTUAL three-bank architecture (user-provided
%   definitions, all cfg constants):
%     pbank 6b : sub-band select, 30 MHz band per code, 15 MHz spacing
%     abank 9b : 511 sub-steps covering the full 30 MHz band
%                (dco_abank_lsb = dco_abank_span/511 ~ 58.7 kHz/code)
%     fbank    : 1-bit mode (dsm_dco_mode=0): ONE cell of 1 abank LSB
%                toggled by a 1st-order SDM fed the full lpf_frac — a
%                single cell must span a full LSB to cover fractions by
%                duty-cycling.  3-bit mode (mode=2, 8 cells of 1/8 LSB,
%                thermometer) retained for comparison.  2026-09-14: both
%                re-evaluated under clk_dsm = DCO/4 (K=20), see README.
%     f_dco = dco_f_lo + pbank*15M + (abank + fbank/8)*(30M/511)
%   AFC (pbank binary search) is fully implemented per rtl/adpll/pbank_afc.v
%   + spec §3 (min-|err| tracking, DCO/afc_div window counting).
%
%   Usage (from algorithm/ADPLL):
%       matlab -batch "addpath('TOP'); top_adpll"               % default
%       matlab -batch "addpath('TOP'); top_adpll('dtc_off')"
%       matlab -batch "addpath('TOP'); top_adpll('no_calib')"
%
%   Outputs -> TOP/output/<scenario>/: fig1..fig5 PNG, metrics.txt,
%   IND_*/DBG_* vector dumps (RM naming/scaling, see README.txt).

if nargin<1, scenario = 'default'; end
if strcmp(scenario,'default'), cfg_file = 'top_cfg.txt';
else, cfg_file = sprintf('top_cfg_%s.txt',scenario); end
top_dir = fileparts(mfilename('fullpath'));
addpath(fullfile(top_dir,'funcs_top'));
addpath(fullfile(top_dir,'..','funcs'));

% ---- golden funcs hold persistent state: reset for a fresh run -------------
clear fll lpf lock_detect calib_kdtc calib_ref_double calib_dco_duty calib_inl

cfg = read_cfg_txt(fullfile(top_dir,'cfg',cfg_file));
if nargin>=2 && ~isempty(cfg_over)        % noise-budget solo-run overrides
    fns_o = fieldnames(cfg_over);
    for k_o = 1:numel(fns_o), cfg.(fns_o{k_o}) = cfg_over.(fns_o{k_o}); end
end
cfg.scenario_name = scenario;
outdir = fullfile(top_dir,'output',scenario);
if isfield(cfg,'outdir_name')             % separate output dir without a cfg file
    outdir = fullfile(top_dir,'output',cfg.outdir_name);
end
if ~exist(outdir,'dir'), mkdir(outdir); end
fid_log = fopen(fullfile(outdir,'run.log'),'w');

if isfield(cfg,'seed'), rng(cfg.seed); end

fcw   = cfg.adpll_fcw/2^35;
fref  = cfg.fref;
Tdco  = 1/(fcw*fref);
N     = round(cfg.n_cycles);
Ka    = cfg.dco_abank_span/511;         % abank LSB [Hz/code]

log_line(fid_log,sprintf('=== top_adpll: scenario=%s  FCW=%.6f (%.6f GHz)  N=%d (%.3f ms) ===', ...
    scenario, fcw, fcw*fref/1e9, N, N/fref*1e3));
log_line(fid_log,sprintf('    DCO: f_lo=%.4f GHz, pbank step %.1f MHz, abank LSB %.1f kHz (span %.0f MHz/511)', ...
    cfg.dco_f_lo/1e9, cfg.dco_pbank_step/1e6, Ka/1e3, cfg.dco_abank_span/1e6));

% ================= per-module cfg structs (mirror of each RM '%% param') ====
cfg_pfd = struct('phe_inv_en',cfg.phe_inv_en, ...
                 'tdc_norm_coef',cfg.tdc_norm_coef, ...
                 'phe_sh',cfg.phe_sh);

cfg_fb = struct('fcw',fcw,'fcw_int_width',13,'fcw_frac_width',35, ...
                'dsm_fb_mode',cfg.dsm_fb_mode,'dsm_fb_dither',cfg.dither_fb_en, ...
                'ref_double_en',cfg.ref_double_en,'sel_clk_fb_en',cfg.sel_clk_fb_en, ...
                'near_integer_mode',cfg.near_integer_mode,'dsm_fb_en',cfg.dsm_fb_en);

cfg_fll = struct('freq_frac_width',15,'fcw_int_width',13,'fcw_frac_width',35, ...
                 'adpll_fcw',fcw, ...
                 'freq_ref_cnt_thr',cfg.freq_ref_cnt_thr, ...
                 'freq_lock_step',cfg.freq_lock_step, ...
                 'freq_lock_thr',cfg.freq_lock_thr, ...
                 'freq_lock_en',0);                       % dynamic (FSM)
% calc_cnt with EXACTLY fll.m's float ops
shift_right = floor(2^cfg_fll.fcw_frac_width*cfg_fll.adpll_fcw/2^2)/2^cfg_fll.fcw_frac_width;
calc_cnt    = floor(shift_right*2^cfg_fll.freq_ref_cnt_thr);

cfg_lpf = struct('lpf_frac_width',26,'phe_frac_width',16,'freq_ctrl_frac_width',15, ...
                 'kp_frac_width',8,'ki_frac_width',10, ...
                 'kp1',cfg.kp1,'ki1',cfg.ki1,'kp2',cfg.kp2,'ki2',cfg.ki2, ...
                 'open_loop_en',0,'Abank_code_sw',256);  % FSM AFC: mid code 256 (spec)

cfg_lock = struct('lock_phe_thr',cfg.lock_phe_thr,'lock_cnt_thr',cfg.lock_cnt_thr, ...
                  'unlock_phe_thr',cfg.unlock_phe_thr,'unlock_cnt_thr',cfg.unlock_cnt_thr);

cfg_kdtc = struct('phe_frac_width',16,'kdtc_qe_frac_width',35,'kdtc_frac_width',24, ...
                  'kdtc_calib_mode',0,'kdtc_initial',cfg.kdtc_initial, ...
                  'kdtc_calib_en',0, ...                               % dynamic (FSM AND cfg)
                  'kdtc_calib_step',1/2^cfg.kdtc_calib_step, ...
                  'dtc_offset',cfg.dtc_offset/2^35);

% DTC plant (golden funcs/dtc.m): delay(code+1) = (code+1)*dtc_lsb cycles.
% Per-code INL/DNL (spec: INL 2 LSB, DNL 1 LSB) and PN-floor jitter are added
% below in the stimulus section (dtc_inl_table/dtc_pn_sigma).
cfg_dtc = struct('dtc_width',10, ...
                 'dtc_delay',cfg.dtc_lsb_cycles*(1:2^10)', ...
                 'dtc_inl',zeros(2^10,1),'dtc_ofst',0);

cfg_refdcc = struct('phe_frac_width',16,'ref_double_calib_mode',0, ...
                    'ref_calib_coef_frac_width',31, ...
                    'ref_double_en',cfg.ref_double_en, ...
                    'ref_double_calib_en',0, ...                        % dynamic
                    'ref_double_calib_step',1/2^cfg.ref_double_calib_step, ...
                    'ref_double_calib_sel',cfg.ref_double_calib_sel);

cfg_dcodcc = struct('phe_frac_width',16,'dco_calib_coef_frac_width',31, ...
                    'dco_duty_calib_mode',0,'dco_duty_calib_sel',0, ...
                    'dco_duty_calib_en',0, ...                          % dynamic
                    'dco_duty_calib_step',1/2^cfg.dco_duty_calib_step);

% 2nd-order DTC INL calibration (golden funcs/calib_inl.m): g2 estimates the
% quadratic DTC INL coefficient from E[phe*eq^2]; correction applies
% round(g2*eq^2/dtc_lsb) to the DTC code (g2 converges to -dtc_inl2_a).
cfg_inl = struct('inl_calib_en',0, ...                                % dynamic (FSM AND cfg)
                 'inl_calib_step',cfg.inl_calib_step, ...
                 'fref',fref, ...
                 'kdtc_frac_width',24, ...
                 'kdtc_calib_mode',0);

% AFC expected count (spec semantics; RTL placeholder is trial_code<<8)
afc_expected = fcw/cfg.afc_fb_div * 2^cfg.afc_ref_cnt_thr;

% ================= plant / stimulus =========================================
pn10  = gen_lfsr_pn10(N);
% DCO phase noise: white (optional) + colored 1/f^n.  Two colored modes
% (check_units validates the synthesized PSD against the target within ~1 dB):
%   piecewise cfg 'dco_pn_spec_f_hz'/'dco_pn_spec_dbc' (comma lists, measured
%   multi-knee spec, log-log interpolated, end slopes extrapolated), or the
%   legacy single-slope line via dco_pn_l1m_dbc/dco_pn_slope_dbdec/dco_pn_floor_dbc
dco_pn = zeros(N,1);
if isfield(cfg,'dco_pn_rms_fs') && cfg.dco_pn_rms_fs>0
    dco_pn = cfg.dco_pn_rms_fs*1e-15/Tdco*randn(N,1);
end
f_pn_tbl = []; l_pn_tbl = [];
if isfield(cfg,'dco_pn_spec_f_hz') && ~isempty(cfg.dco_pn_spec_f_hz)
    f_pn_tbl = str2double(strsplit(char(cfg.dco_pn_spec_f_hz),','));
    l_pn_tbl = str2double(strsplit(char(cfg.dco_pn_spec_dbc),','));
end
if numel(f_pn_tbl)>=2 && numel(f_pn_tbl)==numel(l_pn_tbl)
    pn_abs = pn_gen_1f3(N,fref,0,-500,0,f_pn_tbl(:),l_pn_tbl(:))/(2*pi);  % cycles, ABSOLUTE phase
    dco_pn = dco_pn + [0; diff(pn_abs)];   % inject the DIFFERENCE: phi = ideal + pn_abs(i)
    log_line(fid_log,sprintf('    DCO PN spec: piecewise %d pts (f Hz,dBc/Hz): %s | %s', ...
        numel(f_pn_tbl), strjoin(string(f_pn_tbl),','), strjoin(string(l_pn_tbl),',')));
elseif isfield(cfg,'dco_pn_l1m_dbc') && cfg.dco_pn_l1m_dbc > -300
    if isfield(cfg,'dco_pn_slope_dbdec'), pn_slope = cfg.dco_pn_slope_dbdec; else, pn_slope = 30; end
    pn_abs = pn_gen_1f3(N,fref,cfg.dco_pn_l1m_dbc,cfg.dco_pn_floor_dbc,pn_slope)/(2*pi); % cycles, ABSOLUTE phase
    dco_pn = dco_pn + [0; diff(pn_abs)];   % inject the DIFFERENCE: phi = ideal + pn_abs(i)
    log_line(fid_log,sprintf('    DCO PN: L(1MHz)=%g dBc/Hz, %g dB/dec to floor %g dBc/Hz', ...
        cfg.dco_pn_l1m_dbc, pn_slope, cfg.dco_pn_floor_dbc));
end
% TDC INL: smoothed random transfer-curve deviation, RMS = tdc_inl_lsb LSB
if isfield(cfg,'tdc_inl_en') && cfg.tdc_inl_en==1
    raw = conv(randn(288,1), ones(33,1)/33, 'same');   % ~1/16-code correlation length
    raw = raw(1:256); raw = raw - mean(raw);
    cfg.tdc_inl_vec = raw/std(raw)*cfg.tdc_inl_lsb;
    log_line(fid_log,sprintf('    TDC INL: on, RMS %.2f LSB (smoothed random)', cfg.tdc_inl_lsb));
else
    cfg.tdc_inl_vec = [];
end
ref_jit = zeros(N,1);
if isfield(cfg,'ref_jitter_fs') && cfg.ref_jitter_fs>0
    ref_jit = cfg.ref_jitter_fs*1e-15/Tdco*randn(N,1);
end
% DTC per-code INL/DNL per the DTC spec table (INL 2 LSB, DNL 1 LSB):
% smooth random curve + non-accumulating mismatch (see dtc_inl_table).
% dtc_inl_table returns LSB units -> multiply by dtc_lsb_cycles for cycles.
tbl_dtc = dtc_inl_table(2^10,cfg.dtc_inl_lsb,cfg.dtc_dnl_lsb,64);
dtc_inl_rms = std(tbl_dtc);                    % realized INL, LSB (RMS)
dtc_dnl_rms = std([0; diff(tbl_dtc)]);         % realized DNL, LSB (RMS)
cfg_dtc.dtc_inl = tbl_dtc*cfg.dtc_lsb_cycles;
assert(max(abs(cfg_dtc.dtc_inl)) < 0.1, ...
    'DTC INL table exceeds 0.1 cyc — LSB->cycle conversion missing?');
% DTC PN floor (spec <= -160 dBc/Hz at fout = 100 MHz): white jitter on the
% delayed edge, sigma_t = sqrt(2*10^(L/10)*fref/2)/(2*pi*fout) = 159 fs RMS
sig_dtc_t = 0;
if isfield(cfg,'dtc_pn_floor_dbc') && cfg.dtc_pn_floor_dbc > -300
    sig_dtc_t = dtc_pn_sigma(cfg.dtc_pn_floor_dbc,fref,cfg.dtc_pn_fout_hz);
end
dtc_jit = sig_dtc_t/Tdco*randn(N,1);              % DCO-cycle units
log_line(fid_log,sprintf('    DTC spec model: INL %.2f LSB RMS (realized %.2f), DNL %.2f LSB RMS (realized %.2f), PN floor %g dBc/Hz @%.0f MHz = %.1f fs RMS jitter', ...
    cfg.dtc_inl_lsb, dtc_inl_rms, cfg.dtc_dnl_lsb, dtc_dnl_rms, ...
    cfg.dtc_pn_floor_dbc, cfg.dtc_pn_fout_hz/1e6, sig_dtc_t*1e15));
kvco = 0;
if isfield(cfg,'kvco_err_ppm'), kvco = cfg.kvco_err_ppm*1e-6; end
taps_dco = cfg.dsm_dco_mode+1;
sig_fmm = 0;
if isfield(cfg,'fine_mismatch_sigma'), sig_fmm = cfg.fine_mismatch_sigma; end
g_fine   = 1 + sig_fmm*randn(1,8);       % 8-cell fine bank (3-bit fbank mode)
g_fine_1b = 1 + sig_fmm*randn;           % the single cell (1-bit fbank mode)

% ================= state ====================================================
S_fb = []; S_dco = []; A_afc = [];
P = struct('phi',0,'tgt',0,'ctrl_prev',0,'ratio',0,'f_dco',0, ...
           'wcnt',0,'phi_ws',0,'fb_delta',0,'wcnt_max',2^cfg.freq_ref_cnt_thr, ...
           'awcnt',0,'ap_ws',0,'afc_delta',0, ...
           'afc_wmax',2^cfg.afc_ref_cnt_thr,'afc_div',cfg.afc_fb_div, ...
           'f_lo',cfg.dco_f_lo,'pstep',cfg.dco_pbank_step,'alsb',Ka, ...
           'fref',fref);
pbank_reg = 0;                          % DCO sub-band select (from AFC)
eq_hist = [0;0];                        % delay line for the kdtc LMS
kdtc_reg  = cfg.kdtc_initial;
g2_reg    = 0;                          % 2nd-order DTC INL coefficient (calib_inl)
comp_reg  = 0;                          % dco_dtc_comp
refcc_reg = 0;                          % ref_calib_comp
fsm = 0; freq_lock = 0; phase_lock = 0; afc_finish = 0;
phe_q_prev = 0;
prev_rstn_fll = 0;
prev_code8 = round(0);

% ---- logs ------------------------------------------------------------------
L = struct();
L.tus = (0:N-1)'/fref*1e6;
L.ratio=zeros(N,1); L.eq=zeros(N,1); L.psel=zeros(N,1); L.dsm_out_fb=zeros(N,1);
L.arb=zeros(N,1); L.ca=zeros(N,1); L.cb=zeros(N,1); L.ft=zeros(N,1);
L.fb_cnt_in=zeros(N,1); L.freq_ctrl_q=zeros(N,1); L.fll_err=zeros(N,1); L.freq_lock=zeros(N,1);
L.lpf_out=zeros(N,1); L.abank=zeros(N,1); L.lpf_frac_q=zeros(N,1);
L.dsm_out_dco=zeros(N,1); L.dcode=zeros(N,1); L.ctrl_tot=zeros(N,1);
L.dtc_code=zeros(N,1); L.tau=zeros(N,1); L.x=zeros(N,1);
L.phe_q=zeros(N,1); L.phe_i16=zeros(N,1); L.phase_lock=zeros(N,1);
L.kdtc=zeros(N,1); L.g2=zeros(N,1); L.dco_dtc_comp=zeros(N,1); L.ref_calib_comp=zeros(N,1);
L.fsm=zeros(N,1); L.rstn=zeros(N,6);       % fll lpf lock dsm_fb dsm_dco calib
L.oh_a=zeros(N,1); L.oh_b=zeros(N,1); L.dither=zeros(N,1);
L.freq_shift=zeros(N,1); L.calc_cnt=zeros(N,1);
L.f_dco=zeros(N,1); L.pbank=zeros(N,1); L.afc_finish=zeros(N,1);
L.phi_abs=zeros(N,1);                  % absolute DCO phase incl. injected PN

for i=1:N
    % ---- (0) FSM: controls from current state, flags from previous cycle --
    [fsm_next,ctl] = fsm_adpll(fsm,afc_finish,freq_lock,phase_lock,cfg);

    % ---- (1) feedback DSM (uses ref_calib_comp of the previous cycle) -----
    if isfield(cfg,'dsm_fb_ideal') && cfg.dsm_fb_ideal==1
        % ideal fractional divide, eq=0 (noise-budget solo runs: removes DSM
        % quantization while keeping the loop at the same operating point)
        ratio = fcw; psel = 0; eq = 0; dsm_out_fb = 0;
    else
        [ratio,psel,eq,dsm_out_fb,~,~,~,S_fb] = dsm_modified_i(ctl.rstn_dsm_fb,refcc_reg,pn10(i),S_fb,cfg_fb);
    end
    eq_hist = [eq; eq_hist(1)];   % delay line for the kdtc LMS (pushed here so
                                  % kdtc_lms_delay=0 correlates phe(i) with eq(i))

    % ---- (2) DTC code from CURRENT q_err, registered kdtc/comp (RM rule) --
    % 2nd-order predistortion from the INL calibrator (g2 -> -dtc_inl2_a)
    dtc_code = round((cfg_kdtc.dtc_offset + eq)*kdtc_reg) + comp_reg ...
               + round(g2_reg*eq^2/cfg.dtc_lsb_cycles);
    dtc_code = min(max(dtc_code,0),1023);
    if cfg.dtc_en==1
        % plant: per-code INL/DNL table (spec) + optional quadratic term
        % (dtc_inl2_a, now 0) + PN-floor white edge jitter
        tau = dtc(dtc_code,cfg_dtc) + cfg.dtc_inl2_a*eq^2 + dtc_jit(i);
    else
        tau = 0;
    end

    % ---- (3) plant: physical DCO, divider edge, TDC residual, counters -----
    [P,x,fb_fresh,afc_fresh,f_dco] = plant_update(P,ratio,tau,pbank_reg, ...
        ctl.freq_lock_en,ctl.rstn_fll,ctl.afc_calib_en,dco_pn(i));
    if fb_fresh==1, fb_cnt_in = P.fb_delta; else, fb_cnt_in = calc_cnt; end
    % first active FLL call: fll.m's calc_cnt_reg is still 0 (it latches calc
    % at the END of the first call) — feeding 0 keeps err=0 (rtl fll.v
    % initializes fb_count_delta to the expected count for exactly this).
    if ctl.rstn_fll==1 && prev_rstn_fll==0
        fb_cnt_in = 0;
    end
    prev_rstn_fll = ctl.rstn_fll;

    % ---- (3b) AFC binary search (consumes this cycle's afc pulse) ---------
    [pbank_new,afc_finish,A_afc] = afc_bisect(A_afc,afc_fresh,P.afc_delta,afc_expected,ctl.afc_calib_en);
    pbank_reg = pbank_new;

    % ---- (4) FLL (pulse convention: real delta only on the window cycle) --
    cfg_fll.freq_lock_en = ctl.freq_lock_en;
    [freq_ctrl,freq_lock,~,fll_err,freq_shift] = fll(ctl.rstn_fll,fb_cnt_in,cfg_fll);
    freq_ctrl_q = round(freq_ctrl*2^15)/2^15;

    % ---- (5) TDC front end + PFD (measures THIS cycle's residual) ---------
    if isfield(cfg,'tdc_ideal') && cfg.tdc_ideal==1
        % infinite-resolution TDC (noise-budget solo runs): mod-1 wrap kept,
        % no 1/256 quantization / INL / one-hot encoding
        xj = x + ref_jit(i);
        xj = xj - round(xj);
        arb = double(xj>=0); ca = 0; cb = 0; ft = 0;
        phe_out = xj; oh_a = 0; oh_b = 0;
    else
        [arb,ca,cb,ft] = tdc_encode(x + ref_jit(i),cfg);
        [phe_out,oh_a,oh_b] = pfd(arb,ca,cb,ft,cfg_pfd);
    end
    phe_i16 = round(phe_out*2^16);
    phe_q   = phe_i16/2^16;

    % ---- (6) LPF (phe of previous cycle; open-loop 256 during AFC) --------
    cfg_lpf.open_loop_en = ctl.lp_open;
    lpf_out = lpf(ctl.rstn_lpf,phase_lock,1,freq_lock,phe_q_prev,freq_ctrl_q,cfg_lpf);
    abank = min(max(floor(lpf_out),0),511);     % (u,9,0) clamp
    lpf_frac_q = round((lpf_out-abank)*2^26)/2^26;

    % ---- (7) fbank: dsm_dco (free-running, K sub-steps per ref cycle) -----
    % 1-bit fine bank (taps_dco==1, dsm_dco_mode=0): a single cell of ONE
    % abank LSB toggled by the 1st-order SDM ({0,1} output).  The full
    % lpf_frac goes into the modulator (no static floor needed), so the mean
    % control is exactly abank + lpf_frac.  Residual phase ripple is
    % Ka/(K*fref) ~ 3.7 fs at K=20 (the SDM accumulator bounds the error).
    % A single cell MUST span a full LSB: a 1-bit {0,1} output realizes means
    % in [0, u] by duty-cycling, so u >= 1 LSB is required to cover [0,1).
    % 3-bit path (taps_dco==3): 8 thermometer steps of 1/8 LSB, DSM input
    % mod(8f,1), static floor(8f) carries through.
    K = cfg.dsm_dco_oversample;
    y_acc = 0;
    if taps_dco==1
        r_dsm = lpf_frac_q;               % whole fraction into the 1-bit SDM
        for m=1:K
            [dsm_out_dco_m,~,S_dco] = dsm_mash_i(r_dsm,26,1,cfg.dither_dco_en,pn10(i),S_dco,1);
            y_acc = y_acc + dsm_out_dco_m;
        end
        code_total = y_acc/K;             % abank-LSB units, mean = lpf_frac
        ctrl_tot = max((abank + code_total*g_fine_1b)*(1+kvco),0);
        dcode = min(max(round(code_total),0),1);      % 1-bit fine code for the log
    else
        f8 = lpf_frac_q*8;
        n_stat = floor(f8);
        r_dsm = f8 - n_stat;
        for m=1:K
            [dsm_out_dco_m,~,S_dco] = dsm_mash_i(r_dsm,26,taps_dco,cfg.dither_dco_en,pn10(i),S_dco,1);
            y_acc = y_acc + dsm_out_dco_m;
        end
        code_total = n_stat + y_acc/K;    % 1/8-LSB units, mean = 8*lpf_frac
        ctrl_tot = max((abank + code_total/8*g_fine(1+min(max(round(code_total),0),7)))*(1+kvco),0);
        dcode = mod(min(max(round(code_total),0),7),8);   % fine thermometer code for the log
    end
    dsm_out_dco = dsm_out_dco_m;
    P.ctrl_prev = ctrl_tot;               % consumed by plant in cycle i+1

    % ---- (7b) code-switch glitch: cap switching injects a one-shot phase  ---
    % kick per unit-code change (fbank unit = 1/8 abank LSB; abank step = 8
    % units, capped to skip control-MODE transitions).  Injected at the cycle
    % boundary -> visible to the TDC next cycle.
    if isfield(cfg,'dco_glitch_fs_per_code') && cfg.dco_glitch_fs_per_code>0
        code_now8 = round(ctrl_tot*8);
        if i>1
            dstep = min(abs(code_now8 - prev_code8), 8);
            P.phi = P.phi + cfg.dco_glitch_fs_per_code*1e-15/Tdco * dstep * randn;
        end
        prev_code8 = code_now8;
    end

    % ---- (8) lock detect (registers internally; flags feed FSM next cycle)
    [phase_lock,~] = lock_detect(ctl.rstn_lock,phe_i16,cfg_lock);

    % ---- (9) background calibrations (golden; enables FSM-ANDed) ----------
    % LMS correlation delay: phe(i) carries the A-sawtooth of eq(i) (the TDC
    % mod-1 aliasing absorbs the integer part of the one-step look-ahead), so
    % the correct alignment here is lag 0.  cfg.kdtc_lms_delay reproduces the
    % RM's fixed 2-sample delay (which anti-converges at frac=0.25).
    lms_delay = round(cfg.kdtc_lms_delay);
    eq_lms = eq_hist(lms_delay+1);
    kdtc_start = double(ctl.kdtc_calib_en==1 && cfg.kdtc_calib_en==1);
    cfg_kdtc.kdtc_calib_en = kdtc_start;
    [kdtc_reg,~] = calib_kdtc(kdtc_start,ctl.rstn_calib,phe_q,eq_lms,cfg_kdtc);

    cfg_refdcc.ref_double_calib_en = double(ctl.ref_double_calib_en==1 && cfg.ref_double_calib_en==1);
    [~,~,refcc_reg] = calib_ref_double(phe_q,ctl.rstn_calib,cfg_refdcc);

    dco_start = double(ctl.dco_duty_calib_en==1 && cfg.dco_duty_calib_en==1);
    cfg_dcodcc.dco_duty_calib_en = dco_start;
    [~,~,comp_reg] = calib_dco_duty(dco_start,ctl.rstn_calib,phe_q,psel,cfg_dcodcc);

    % 2nd-order DTC INL calibration (golden): phe(i) x eq(i)^2 correlator with
    % its own 150us start delay; applied to the DTC code from the next cycle.
    % Sequenced AFTER the kdtc LMS has converged (cfg.inl_calib_start_cycle):
    % the two correlators couple through E[eq^3] != 0 (one-sided sawtooth), and
    % a simultaneous start leaves a very slow coupled transient.
    cfg_inl.inl_calib_en = double(ctl.kdtc_calib_en==1 && cfg.inl_calib_en==1 ...
                                  && i >= cfg.inl_calib_start_cycle);
    [g2_reg,~] = calib_inl(ctl.rstn_calib,phe_q,eq,cfg_inl);

    % ---- (10) logs ---------------------------------------------------------
    L.ratio(i)=ratio; L.eq(i)=eq; L.psel(i)=psel; L.dsm_out_fb(i)=dsm_out_fb;
    L.arb(i)=arb; L.ca(i)=ca; L.cb(i)=cb; L.ft(i)=ft;
    L.fb_cnt_in(i)=fb_cnt_in; L.freq_ctrl_q(i)=freq_ctrl_q; L.fll_err(i)=fll_err;
    L.freq_lock(i)=freq_lock; L.lpf_out(i)=lpf_out; L.abank(i)=abank;
    L.lpf_frac_q(i)=lpf_frac_q; L.dsm_out_dco(i)=dsm_out_dco; L.dcode(i)=dcode;
    L.ctrl_tot(i)=ctrl_tot; L.dtc_code(i)=dtc_code; L.tau(i)=tau; L.x(i)=x;
    L.phe_q(i)=phe_q; L.phe_i16(i)=phe_i16; L.phase_lock(i)=phase_lock;
    L.kdtc(i)=kdtc_reg; L.g2(i)=g2_reg; L.dco_dtc_comp(i)=comp_reg; L.ref_calib_comp(i)=refcc_reg;
    L.fsm(i)=fsm;
    L.rstn(i,:)=[ctl.rstn_fll ctl.rstn_lpf ctl.rstn_lock ctl.rstn_dsm_fb ctl.rstn_lpf ctl.rstn_calib];
    L.oh_a(i)=oh_a; L.oh_b(i)=oh_b; L.dither(i)=pn10(i);
    L.freq_shift(i)=freq_shift; L.calc_cnt(i)=calc_cnt;
    L.f_dco(i)=f_dco; L.pbank(i)=pbank_reg; L.afc_finish(i)=afc_finish;
    L.phi_abs(i)=P.phi;

    phe_q_prev = phe_q;
    fsm = fsm_next;
end

% ================= metrics / plots / dumps ==================================
L.phi_abs_err = L.phi_abs - (1:N)'*fcw;     % output phase error, DCO cycles
M = metrics_calc(L,cfg,calc_cnt);
log_line(fid_log,sprintf('afc: pbank=%d (f0=%.4f GHz), finish@%.1f us', ...
    L.pbank(end), cfg.dco_f_lo/1e9 + L.pbank(end)*cfg.dco_pbank_step/1e9, ...
    find(L.afc_finish==1,1)/fref*1e6));
log_line(fid_log,sprintf('abank_final=%.2f, freq_ctrl_final=%.3f', M.abank_final, M.freq_ctrl_final));
log_line(fid_log,sprintf('fll_lock_time  = %.2f us',M.fll_lock_time_us));
log_line(fid_log,sprintf('lock_time_us   = %.2f  (spec 200)',M.lock_time_us));
log_line(fid_log,sprintf('phe_rms_fs     = %.2f  (spec 200; TDC quant-noise floor ~%.0f fs)',M.phe_rms_fs, 2^-8*Tdco*1e15/sqrt(12)));
log_line(fid_log,sprintf('freq_err_hz    = %.1f (%.3f ppm)',M.freq_err_hz,M.freq_err_ppm));
log_line(fid_log,sprintf('kdtc_final     = %.2f (target %.1f, err %.2f%%)',M.kdtc_final,M.kdtc_target,M.kdtc_err_pct));
log_line(fid_log,sprintf('frac spur      = %.2f dBc  (rms %.2e cyc)',M.spur_dbc,M.spur_rms_cyc));
log_line(fid_log,sprintf('2nd-harm spur  = %.2f dBc  (rms %.2e cyc)',M.spur2_dbc,M.spur2_rms_cyc));
log_line(fid_log,sprintf('g2_final       = %.5f (target %.5f)',M.g2_final,M.g2_target));

plot_results(L,M,cfg,outdir);
dump_vectors(L,outdir);
dump_metrics(M,calc_cnt,outdir);
write_readme(cfg,calc_cnt,outdir);
log_line(fid_log,sprintf('outputs -> %s',outdir));
fclose(fid_log);
end

% =============================================================================
function log_line(fid,s)
fprintf('%s\n',s);
if fid~=-1, fprintf(fid,'%s\n',s); end
end

function dump_vectors(L,outdir)
% IND/DBG dumps: one %d per line (funcs/data_save.m), RM naming and scaling.
DBG = struct();
DBG.phe_out           = L.phe_i16;         % (s,18,16) LSBs (RM dumps float; see README)
DBG.phe_abs_out       = abs(L.phe_i16);
DBG.phe_flag_out      = L.phase_lock;
DBG.phase_lock_out    = L.phase_lock;
DBG.abank_code        = L.abank;
DBG.lpf_frac          = round(L.lpf_frac_q*2^26);
DBG_freq_ctrl         = round(L.freq_ctrl_q*2^15);
DBG_freq_shift        = round(L.freq_shift*2^15);
DBG_freq_lock         = L.freq_lock;
DBG_calc_cnt          = L.calc_cnt;
DBG_fll_freq_err      = round(L.fll_err);
DBG.dsm_out_fb        = L.dsm_out_fb;
DBG.freq_div_ratio_out= L.ratio;
DBG.q_err_out         = round(L.eq*2^35);
DBG.sel_clk_fb_out    = L.psel;
DBG.dsm_out_dco       = L.dsm_out_dco;
DBG.dsm_code_dco      = L.dcode;
DBG.dtc_code          = L.dtc_code;
DBG.dco_dtc_comp      = L.dco_dtc_comp;
DBG.ref_calib_comp    = round(L.ref_calib_comp*2^31);
DBG.ctdc_in_one_hot_a = L.oh_a;
DBG.ctdc_in_one_hot_b = L.oh_b;
DBG.kdtc              = round(L.kdtc*2^24);
DBG.g2                = round(L.g2*2^24);
DBG.dco_freq_hz       = round(L.f_dco);
DBG.phi_abs_err       = L.phi_abs_err;     % output phase error, DCO cycles
DBG.fsm_state         = L.fsm;
DBG.pbank_code        = L.pbank;
DBG.afc_finish        = L.afc_finish;

fns = fieldnames(DBG);
for k=1:numel(fns)
    data_save(fullfile(outdir,['DBG_' fns{k} '.txt']),double(DBG.(fns{k})));
end
data_save(fullfile(outdir,'DBG_freq_ctrl.txt'),double(DBG_freq_ctrl));
data_save(fullfile(outdir,'DBG_freq_shift.txt'),double(DBG_freq_shift));
data_save(fullfile(outdir,'DBG_calc_cnt.txt'),double(DBG_calc_cnt));
data_save(fullfile(outdir,'DBG_fll_freq_err.txt'),double(DBG_fll_freq_err));

IND = struct();
IND.arb_out           = L.arb;
IND.ctdc_out_a        = L.ca;
IND.ctdc_out_b        = L.cb;
IND.ftdc_out          = L.ft;
IND.phe_out           = L.phe_i16;
IND.phe               = L.phe_i16;        % lock_detect input (RM name IND_phe)
IND.q_err             = round(L.eq*2^35);
IND.freq_ctrl         = round(L.freq_ctrl_q*2^15);
IND.fb_cnt            = L.fb_cnt_in;
IND.lpf_frac          = round(L.lpf_frac_q*2^26);
IND.dither            = L.dither;
IND.ref_calib_comp    = round(L.ref_calib_comp*2^31);
IND.sel_clk_fb        = L.psel;
IND.dco_dtc_comp      = L.dco_dtc_comp;
IND.afc_finish        = L.afc_finish;
IND.kdtc_calib_start  = double(L.fsm>=3);
IND.dco_calib_start   = double(L.fsm>=3);
IND.phase_lock        = [0; L.phase_lock(1:end-1)];   % what LPF actually saw
IND.freq_lock         = L.freq_lock;
IND.rstn_fll          = L.rstn(:,1);
IND.rstn_lpf          = L.rstn(:,2);
IND.rstn_lock         = L.rstn(:,3);
IND.rstn_dsm_fb       = L.rstn(:,4);
IND.rstn_dsm_dco      = L.rstn(:,5);
IND.rstn_calib        = L.rstn(:,6);

fns = fieldnames(IND);
for k=1:numel(fns)
    data_save(fullfile(outdir,['IND_' fns{k} '.txt']),double(IND.(fns{k})));
end
end

function dump_metrics(M,calc_cnt,outdir)
fid = fopen(fullfile(outdir,'metrics.txt'),'w');
fprintf(fid,'afc_finish_time_us: %.3f\n', M.afc_finish_time_us);
fprintf(fid,'pbank_final: %d\n', M.pbank_final);
fprintf(fid,'abank_final: %.3f\n', M.abank_final);
fprintf(fid,'fll_lock_time_us: %.3f\n', M.fll_lock_time_us);
fprintf(fid,'freq_ctrl_final: %.6f\n', M.freq_ctrl_final);
fprintf(fid,'calc_cnt: %d\n', calc_cnt);
fprintf(fid,'fll_freq_err_final: %g\n', M.fll_freq_err_final);
fprintf(fid,'lock_time_us: %.3f\n', M.lock_time_us);
fprintf(fid,'lock_time_spec_us: 200\n');
fprintf(fid,'phe_rms_fs: %.2f\n', M.phe_rms_fs);
fprintf(fid,'phe_rms_spec_fs: 200\n');
fprintf(fid,'freq_err_hz: %.1f\n', M.freq_err_hz);
fprintf(fid,'freq_err_ppm: %.4f\n', M.freq_err_ppm);
fprintf(fid,'kdtc_final: %.3f\n', M.kdtc_final);
fprintf(fid,'kdtc_target: %.3f\n', M.kdtc_target);
fprintf(fid,'kdtc_err_pct: %.3f\n', M.kdtc_err_pct);
fprintf(fid,'g2_final: %.6f\n', M.g2_final);
fprintf(fid,'g2_target: %.6f\n', M.g2_target);
fprintf(fid,'spur2_rms_cyc: %.6e\n', M.spur2_rms_cyc);
fprintf(fid,'spur2_dbc: %.2f\n', M.spur2_dbc);
fprintf(fid,'spur_rms_cyc: %.6e\n', M.spur_rms_cyc);
fprintf(fid,'spur_dbc: %.2f\n', M.spur_dbc);
fclose(fid);
end

function write_readme(cfg,calc_cnt,outdir)
Ka = cfg.dco_abank_span/511;
fid = fopen(fullfile(outdir,'README.txt'),'w');
fprintf(fid,['Top-level ADPLL closed-loop simulation outputs (PHYSICAL three-bank DCO + full AFC)\n' ...
  'Vector files are one integer per line per reference cycle (25 MHz), same conventions as RM/output.\n\n']);
fprintf(fid,'DCO model (actual architecture, user-provided bank definitions):\n');
fprintf(fid,'  pbank 6b : 30 MHz band per code, %.1f MHz spacing (cfg dco_pbank_step)\n', cfg.dco_pbank_step/1e6);
fprintf(fid,'  abank 9b : 511 sub-steps over %.0f MHz -> LSB %.4f kHz (cfg dco_abank_span)\n', cfg.dco_abank_span/1e6, Ka/1e3);
if cfg.dsm_dco_mode==0
    fprintf(fid,['  fbank 1b : TEMPORARY single cell of 1 abank LSB on a 1st-order SDM\n' ...
      '            ({0,1} output, input = full lpf_frac, mean ctrl = abank+lpf_frac)\n']);
else
    fprintf(fid,'  fbank 3b : lpf_frac -> SDM, 8 codes = 1 abank LSB\n');
end
fprintf(fid,'  f_dco = %.4f GHz + pbank*%g + ctrl*%.6f Hz\n', cfg.dco_f_lo/1e9, cfg.dco_pbank_step, Ka);
fprintf(fid,'  loop retune: kp/ki scaled by fref/Ka (=%.0f) vs the normalized model\n\n', 25e6/Ka);
fprintf(fid,['Scaling of the dumped vectors (same conventions as RM/output):\n' ...
  '  DBG/IND_phe_out, IND_phe : (s,18,16) LSBs, cycles = val/2^16\n' ...
  '  DBG/IND_q_err            : (s,36,35) LSBs, DCO cycles = val/2^35\n' ...
  '  DBG/IND_freq_ctrl        : (s,25,15) LSBs, now in abank-code units\n' ...
  '  IND_lpf_frac, DBG_lpf_frac: (u,26,26) LSBs\n' ...
  '  DBG_dco_freq_hz          : physical f_dco (Hz)\n' ...
  '  DBG_kdtc                 : (s,34,24) LSBs\n' ...
  '  DBG_pbank_code           : AFC-selected sub-band (6b)\n\n']);
fprintf(fid,['FLL fb_cnt convention (pulse): IND_fb_cnt holds the fresh DCO/4 window\n' ...
    'count only on the first cycle of each %d-cycle window and calc_cnt=%d\n' ...
    'otherwise, which makes funcs/fll.m integrate once per window exactly like\n' ...
    'rtl/adpll/fll/fll.v (ref_window_done_d).  Held or live counts diverge.\n\n'], ...
    2^cfg.freq_ref_cnt_thr, calc_cnt);
fprintf(fid,['Modeling decisions (cfg-switchable):\n' ...
  ' A. dsm_dco FREE-RUNS (adpll_fsm.v does not drive rstn_dsm_dco) at\n' ...
  '    dsm_dco_oversample sub-steps per ref cycle; resetting it during FLL\n' ...
  '    pins the fine bank -> 25 MHz-ish deadband, ref-rate dither breaks FLL.\n' ...
  ' B. Fine bank: 8 codes = 1 abank LSB, DSM input mod(8f,1) + static floor(8f)\n' ...
  '    (RM/dsm_dco_rm.m drives lpf_frac directly — placeholder, mean off by f/8).\n' ...
  ' C. FLL first active call feeds fb_cnt=0 (fll.m latches calc_cnt_reg one\n' ...
  '    call late; rtl/adpll/fll/fll.v initializes fb_count_delta for this).\n' ...
  ' D. kdtc LMS at LAG 0 (cfg.kdtc_lms_delay): the RM fixed 2-sample delay\n' ...
  '    anti-converges at frac=0.25 (period-4 sawtooth, half-period lag).\n' ...
  ' E. lpf.m quantizes ki to the 2^-10 grid: ki < 2^-10 rounds to ZERO.\n' ...
  ' F. FLL loop gain is Kvco-limited (Ka/(4*fref) per cycle): with the physical\n' ...
  '    58.7 kHz abank LSB the count LSB (195 kHz @ 512-cycle DCO/4 window) is\n' ...
  '    3.33x coarser than a code, so freq_ctrl walks at ~0.3 window-gain —\n' ...
  '    freq_lock_thr=15 declares early and the PLL absorbs the remainder.\n' ...
  ' G. 1-bit fbank (dsm_dco_mode=0): single cell of 1 abank LSB on a\n' ...
  '    1st-order SDM fed the full lpf_frac; quantization phase ripple is only\n' ...
  '    Ka/(K*fref) ~ 3.7 fs at dsm_dco_oversample=20 (clk_dsm = fDCO/4 =\n' ...
  '    FCW/4 sub-steps per ref cycle; 3-bit path kept, mode=2).\n' ...
  ' H. DTC plant per spec table: per-code INL %.1f LSB RMS (smooth random curve)\n' ...
  '    + DNL %.1f LSB RMS (non-accumulating cell mismatch, see dtc_inl_table)\n' ...
  '    and PN floor %g dBc/Hz @%.0f MHz = %.0f fs RMS white edge jitter\n' ...
  '    (dtc_pn_sigma); the synthetic quadratic dtc_inl2_a is now 0.\n\n'], ...
  cfg.dtc_inl_lsb, cfg.dtc_dnl_lsb, cfg.dtc_pn_floor_dbc, ...
  cfg.dtc_pn_fout_hz/1e6, dtc_pn_sigma(cfg.dtc_pn_floor_dbc,cfg.fref,cfg.dtc_pn_fout_hz)*1e15);
fprintf(fid,['Known RM/RTL discrepancies found while building this sim (model wins here):\n' ...
  ' 1. fll.v expected_count = FCW_int*2^thr vs fll.m calc_cnt = FCW*2^thr/4 (=> fb clock is DCO/4)\n' ...
  ' 2. adpll_fsm.v ST_LOCK drives rstn_fll=0 (would clear freq_ctrl); sim keeps FLL frozen (fsm_lock_keep_fll=1)\n' ...
  ' 3. funcs/lpf.m kp/ki selection is inverted vs the spec table and lpf.v (kp1 = pre-lock there)\n' ...
  ' 4. RM cfg lock_cnt_thr=256 is an exponent (2^256, never locks); top cfg uses 8\n' ...
  ' 5. dco_duty_calibration_cfg.txt IND_sel_clk_fb path points at IND_dco_dtc_comp.txt\n' ...
  ' 6. pbank_afc.v expected_count = trial_code<<8 is an unfinished placeholder;\n' ...
  '    the sim uses the spec semantics expected = FCW/afc_div*2^afc_ref_cnt_thr\n']);
fclose(fid);
end
