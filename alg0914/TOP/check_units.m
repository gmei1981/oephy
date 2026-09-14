% check_units.m — unit checks for the closed-loop top-level sim.
%   Run:  matlab -batch "addpath('TOP'); run('TOP/check_units.m')"
%   (from algorithm/ADPLL).  Each check prints [PASS]/[FAIL].

top_dir = fileparts(mfilename('fullpath'));
addpath(fullfile(top_dir,'funcs_top'));
addpath(fullfile(top_dir,'..','funcs'));

% physical DCO constants from the default scenario cfg (single source)
cfg0 = read_cfg_txt(fullfile(top_dir,'cfg','top_cfg.txt'));
fs0 = cfg0.fref;   % reference clock from cfg (100 MHz in the current setup)
fcw0 = cfg0.adpll_fcw/2^35;
f_lo0 = cfg0.dco_f_lo;  pstep0 = cfg0.dco_pbank_step;  Ka0 = cfg0.dco_abank_span/511;

n_fail = 0;

%% ---- 1. TDC encode -> pfd decode round trip -------------------------------
cfg_pfd = struct('phe_inv_en',1,'tdc_norm_coef',2^-8,'phe_sh',0);
ok = true; worst = 0;
for sgn = [1 -1]
    for v = 0:239
        x = sgn*v/256;
        [arb,ca,cb,ft] = tdc_encode(x,struct('tdc_noise_lsb',0));
        phe = pfd(arb,ca,cb,ft,cfg_pfd);
        expected = x - round(x);        % TDC measures phase mod 1 DCO cycle
        err = abs(phe - expected);
        worst = max(worst,err);
        if err > 0
            ok = false;
            fprintf('   round-trip fail: x=%+.4f  phe=%+.6f  expected %+.6f\n', x, phe, expected);
        end
    end
end
pr('1. TDC round-trip (480 codes, mod-1)', ok); if ~ok, n_fail=n_fail+1; end

%% ---- 2. instance DSMs == golden DSMs --------------------------------------
clear dsm_mash dsm_modified
cfg_fb = struct('fcw',fcw0,'fcw_int_width',13,'fcw_frac_width',35, ...
    'dsm_fb_mode',0,'dsm_fb_dither',0,'ref_double_en',0,'sel_clk_fb_en',0, ...
    'near_integer_mode',0,'dsm_fb_en',1);
n2 = 1000;
rst = [zeros(1,5) ones(1,n2-5)];                 % 5 reset cycles then run
rcc = zeros(1,n2);
pn  = gen_lfsr_pn10(n2)';
S = [];
g_ratio=[]; g_eq=[]; g_dsm=[];
for k=1:n2
    [a,b,c,d] = dsm_modified(rst(k),rcc(k),pn(k),cfg_fb);
    g_ratio(end+1)=a; g_eq(end+1)=c; g_dsm(end+1)=d; %#ok<SAGROW>
end
clear dsm_mash dsm_modified
i_ratio=[]; i_eq=[]; i_dsm=[];
S = [];
for k=1:n2
    [a,~,c,d,~,~,~,S] = dsm_modified_i(rst(k),rcc(k),pn(k),S,cfg_fb);
    i_ratio(end+1)=a; i_eq(end+1)=c; i_dsm(end+1)=d; %#ok<SAGROW>
end
ok = isequal(g_ratio,i_ratio) && isequal(g_eq,i_eq) && isequal(g_dsm,i_dsm);
pr('2a. dsm_modified_i == golden dsm_modified (1000 samples)', ok);
if ~ok, n_fail=n_fail+1; end

clear dsm_mash
fr = repelem([0.1 0.3 0.7],300)';
g_out=[]; for k=1:900, [o,~]=dsm_mash(fr(k),26,3,0,0); g_out(end+1)=o; end %#ok<SAGROW>
clear dsm_mash
i_out=[]; S=[]; for k=1:900, [o,~,S]=dsm_mash_i(fr(k),26,3,0,0,S,1); i_out(end+1)=o; end %#ok<SAGROW>
ok = isequal(g_out,i_out);
pr('2b. dsm_mash_i == golden dsm_mash (MASH-3, 900 samples)', ok);
if ~ok, n_fail=n_fail+1; end

%% ---- 3. dsm_dco thermometer mapping ---------------------------------------
ok = true;
for f = [0 0.25 0.5 0.875]
    clear dsm_mash
    S=[]; acc=0; n=4000;
    for k=1:n
        [o,~,S]=dsm_mash_i(f,26,3,0,0,S,1);
        acc = acc + therm_dco_code(o,3);
    end
    m = acc/n;                                    % mean code
    if abs(m - (3+f)) > 0.02
        ok = false; fprintf('   mean code %.4f, expected %.4f\n', m, 3+f);
    end
end
pr('3. dsm_dco thermometer mean = 3+lpf_frac (code=dsm_out+3)', ok);
if ~ok, n_fail=n_fail+1; end

%% ---- 4. divider conservation: tgt(k) = FCW*k + eq(k+1) --------------------
clear dsm_mash dsm_modified
S=[]; n4=500;
fcw = cfg_fb.fcw;
eqs=[]; ratios=[];
for k=1:n4
    [ratio,~,eq,~,~,~,~,S] = dsm_modified_i(1,0,0,S,cfg_fb);
    eqs(end+1)=eq; ratios(end+1)=ratio; %#ok<SAGROW>
end
% after call k: tgt(k) = sum(ratios(1..k)); post-update accum(k) = eq(k+1)
tgt=0; tgts=[];
for k=1:n4, tgt = tgt + ratios(k); tgts(end+1)=tgt; end %#ok<SAGROW>
worst=0;
for k=1:n4-1
    worst = max(worst, abs((tgts(k) - k*fcw) - eqs(k+1)));
end
ok = worst < 1e-9;
fprintf('   (divider identity |tgt(k)-k*FCW-eq(k+1)| max = %.2e)\n', worst);
pr('4. divider conservation: tgt(k) = k*FCW + eq(k+1)', ok);
if ~ok, n_fail=n_fail+1; end

%% ---- 5. FLL closed through the physical plant (pulse convention) ----------
Ka = Ka0;  f_lo = f_lo0;  pstep = pstep0;
pbk = round((fcw0*fs0 - f_lo - 15e6)/pstep);    % band holding the target
ok5 = true;
for eps = [0 0.01 -0.01]
    clear fll
    cfg_fll = struct('freq_frac_width',15,'fcw_int_width',13,'fcw_frac_width',35, ...
        'adpll_fcw',fcw,'freq_ref_cnt_thr',9,'freq_lock_step',0,'freq_lock_thr',cfg0.freq_lock_thr, ...
        'freq_lock_en',1);
    shift_right = floor(2^35*fcw/2^2)/2^35;
    calc_cnt = floor(shift_right*2^9);
    P = struct('phi',0,'tgt',0,'ctrl_prev',0,'ratio',0,'f_dco',0, ...
        'wcnt',0,'phi_ws',0,'fb_delta',0,'wcnt_max',512, ...
        'awcnt',0,'ap_ws',0,'afc_delta',0,'afc_wmax',128,'afc_div',8, ...
        'f_lo',f_lo,'pstep',pstep,'alsb',Ka,'fref',fs0);
    fc_q = 0; locked_at = NaN; prev_rstn = 0;
    for k=1:20000
        [P,~,fresh] = plant_update(P,200,0,pbk,1,1,0,0);
        if fresh==1, fb_in = P.fb_delta; else, fb_in = calc_cnt; end
        if prev_rstn==0, fb_in = 0; end       % fll.m first-call phantom fix
        prev_rstn = 1;
        [freq_ctrl,freq_lock] = fll(1,fb_in,cfg_fll);
        fc_q = round(freq_ctrl*2^15)/2^15;
        P.ctrl_prev = fc_q*(1+eps);
        if isnan(locked_at) && freq_lock==1, locked_at = k; end
    end
    expect = (fcw*fs0 - (f_lo+pbk*pstep))/Ka/(1+eps);    % abank code for the target
    ok = ~isnan(locked_at) && abs(fc_q-expect) <= 55;    % freq_lock_thr=15 counts ~ 50 codes
    fprintf('   eps=%+.3f: locked@%d, freq_ctrl(code)=%.2f (expect %.2f)\n', eps, locked_at, fc_q, expect);
    if ~ok, ok5 = false; end
end
pr('5. FLL mini-closed-loop converges on physical plant (eps=0/+-1%%)', ok5);
if ~ok5, n_fail=n_fail+1; end

%% ---- 6. DTC plant lookup ----------------------------------------------------
lsb = 1/280;
cfg_dtc = struct('dtc_width',10,'dtc_delay',lsb*(1:1024)','dtc_inl',zeros(1024,1),'dtc_ofst',0);
ok = true;
codes = [0 57 300 560 900 1023 2000 -5];
for c = codes
    tau = dtc(c,cfg_dtc);
    cc = min(max(round(c+1),1),1024);
    if abs(tau - cc*lsb) > 1e-12
        ok = false; fprintf('   dtc(%d)=%.6f expected %.6f\n', c, tau, cc*lsb);
    end
end
pr('6. DTC lookup + clamp (dtc(code)=(code+1)/280 cyc)', ok);
if ~ok, n_fail=n_fail+1; end

%% ---- 7. lock_detect exponent semantics ------------------------------------
clear lock_detect
cfg_lock = struct('lock_phe_thr',5000,'lock_cnt_thr',8,'unlock_phe_thr',20000,'unlock_cnt_thr',4);
first_lock = NaN;
for k=1:300
    [pl,~] = lock_detect(1,100,cfg_lock);
    if isnan(first_lock) && pl==1, first_lock = k; end
end
ok = first_lock==257;   % output is pre-update lock_reg: lock_reg set at call 2^8, visible at call 2^8+1
fprintf('   first phase_lock=1 at call %d (expect 257 = 2^8+1)\n', first_lock);
pr('7. lock_detect 2^cnt_thr exponent semantics', ok);
if ~ok, n_fail=n_fail+1; end

%% ---- 8. physical DCO bank gains -------------------------------------------
P8 = struct('phi',0,'tgt',0,'ctrl_prev',100,'ratio',0,'f_dco',0, ...
    'wcnt',0,'phi_ws',0,'fb_delta',0,'wcnt_max',512, ...
    'awcnt',0,'ap_ws',0,'afc_delta',0,'afc_wmax',128,'afc_div',8, ...
    'f_lo',f_lo,'pstep',pstep,'alsb',Ka,'fref',fs0);
[~,~,~,~,fd1] = plant_update(P8,0,0,5,0,0,0,0);
P8.ctrl_prev = 101;
[~,~,~,~,fd2] = plant_update(P8,0,0,5,0,0,0,0);
[~,~,~,~,fd3] = plant_update(P8,0,0,6,0,0,0,0);
ok = abs(fd2-fd1-Ka) < 1e-6 && abs(fd3-fd2-pstep) < 1e-6;
fprintf('   abank +1 code: %.2f Hz (expect %.2f); pbank +1 code: %.1f Hz (expect %.1f)\n', fd2-fd1, Ka, fd3-fd2, pstep);
pr('8. physical DCO gains (abank LSB = span/511, pbank = cfg step)', ok);
if ~ok, n_fail=n_fail+1; end

%% ---- 9. AFC selects the right sub-band ------------------------------------
ok9 = true;
for tgt_fcw = [7.7 8.025 8.85]*1e9/fs0         % low/mid/high of 7.67-8.9 GHz
    f_tgt = tgt_fcw*fs0;
    exp_afc = tgt_fcw/8*2^cfg0.afc_ref_cnt_thr;
    P9 = struct('phi',0,'tgt',0,'ctrl_prev',256,'ratio',0,'f_dco',0, ...
        'wcnt',0,'phi_ws',0,'fb_delta',0,'wcnt_max',512, ...
        'awcnt',0,'ap_ws',0,'afc_delta',0,'afc_wmax',2^cfg0.afc_ref_cnt_thr,'afc_div',8, ...
        'f_lo',f_lo,'pstep',pstep,'alsb',Ka,'fref',fs0);
    A9 = []; pbk9 = 32; fin = 0;
    for k=1:8000
        [P9,~,~,af_fresh] = plant_update(P9,0,0,pbk9,0,0,1,0);
        [pbk9,fin,A9] = afc_bisect(A9,af_fresh,P9.afc_delta,exp_afc,1);
        if fin==1, break; end
    end
    resid = f_tgt - (f_lo + pbk9*pstep);           % must be coverable by abank [0,30M]
    ok = fin==1 && resid > -3e6 && resid < 33e6;
    fprintf('   FCW=%.2f (%.4f GHz): pbank=%d, residual=%.2f MHz, finish@%d\n', ...
        tgt_fcw, f_tgt/1e9, pbk9, resid/1e6, k);
    if ~ok, ok9 = false; end
end
pr('9. AFC binary search selects a coverable sub-band (7.7/8.0/8.85 GHz)', ok9);
if ~ok9, n_fail=n_fail+1; end

%% ---- 10. colored DCO PN synthesis matches the target PSD -------------------
N10 = 2^18;  fs10 = fs0;
if isfield(cfg0,'dco_pn_spec_f_hz') && ~isempty(cfg0.dco_pn_spec_f_hz)
    % piecewise measured spec: log-log interpolation through the table
    f_tbl = str2double(strsplit(char(cfg0.dco_pn_spec_f_hz),','));
    l_tbl = str2double(strsplit(char(cfg0.dco_pn_spec_dbc),','));
    pn10v = pn_gen_1f3(N10,fs10,0,-500,0,f_tbl(:),l_tbl(:));   % radians
    tgt = @(f) interp1(log10(f_tbl(:)), l_tbl(:), log10(f), 'linear','extrap');
    ttl = sprintf('10. DCO colored PN synthesis (piecewise %d-pt spec; PSD +-3 dB)', numel(f_tbl));
    fchk = [5e3 2e4 1e5 1e6 1e7];
else
    if isfield(cfg0,'dco_pn_slope_dbdec'), sl10 = cfg0.dco_pn_slope_dbdec; else, sl10 = 30; end
    pn10v = pn_gen_1f3(N10,fs10,cfg0.dco_pn_l1m_dbc,cfg0.dco_pn_floor_dbc,sl10);   % radians
    tgt = @(f) max(cfg0.dco_pn_floor_dbc, cfg0.dco_pn_l1m_dbc + sl10*log10(1e6./f));
    ttl = sprintf('10. DCO colored PN synthesis (%g dBc/Hz@1MHz, %g dB/dec, floor %g; PSD +-3 dB)', ...
        cfg0.dco_pn_l1m_dbc, sl10, cfg0.dco_pn_floor_dbc);
    fchk = [5e3 2e4 1e5];
end
X10 = fft(pn10v - mean(pn10v));
P10 = (abs(X10(2:N10/2)).^2)*2/(N10*fs10);           % one-sided rad^2/Hz
f10 = (1:N10/2-1)'*fs10/N10;
L10 = 10*log10(P10/2);                               % dBc/Hz
ok10 = true;
for fq = fchk
    win = abs(f10-fq) < 0.10*fq;               % +-10% band average
    Lm = mean(L10(win));
    e = Lm - tgt(fq);
    fprintf('   f=%7.0f Hz: measured %.1f dBc/Hz, target %.1f (err %+.1f dB)\n', fq, Lm, tgt(fq), e);
    if abs(e) > 3.0, ok10 = false; end        % periodogram single-run variance ~+-3 dB
end
pr(ttl, ok10);
if ~ok10, n_fail=n_fail+1; end

%% ---- 11. TDC INL applied and traceable -------------------------------------
t11 = zeros(256,1); t11(40:60) = 2.5; t11(100:120) = -2.0;   % known table
cfg11 = struct('tdc_noise_lsb',0,'tdc_inl_vec',t11);
worst11 = 0;
for v = 0:5:128                                      % linear range (no mod-1 wrap)
    [arb,ca,cb,ft] = tdc_encode(v/256,cfg11);
    phe = pfd(arb,ca,cb,ft,cfg_pfd);
    expected = min(max(round(v + t11(v+1)),0),239)/256;
    worst11 = max(worst11, abs(phe - expected));
end
ok11 = worst11 <= 1/256 + 1e-12;
fprintf('   worst INL round-trip error = %.2f LSB\n', worst11*256);
pr('11. TDC INL lookup in encode -> pfd decode', ok11);
if ~ok11, n_fail=n_fail+1; end

%% ---- 12. 2nd-order DTC INL calibrator converges -----------------------------
clear calib_inl
alpha12 = 0.02;                                    % plant quadratic INL (cycles)
cfgI = struct('inl_calib_en',1,'inl_calib_step',1/256,'fref',25e6, ...
              'kdtc_frac_width',24,'kdtc_calib_mode',0);
eqpat = repmat([0 -0.25 -0.5 -0.75]',1,8000);      % MASH-1 sawtooth, frac=0.25
g2app = 0;                                         % correction applied (mini loop)
for k = 1:numel(eqpat)
    phe_k = -(alpha12 + g2app)*eqpat(k)^2;         % residual after correction
    [g2app,~] = calib_inl(1,phe_k,eqpat(k),cfgI);  % g2 = pre-update (registered)
end
err12 = abs(g2app - (-alpha12));
fprintf('   g2 converged to %.5f (target %.5f, err %.1f%%)\n', g2app, -alpha12, 100*err12/alpha12);
ok12 = err12 < 0.05*alpha12;
pr('12. calib_inl 2nd-order correlator converges to -alpha', ok12);
if ~ok12, n_fail=n_fail+1; end

%% ---- 13. DTC INL/DNL table meets the spec ------------------------------------
% spec: INL 2 LSB, DNL 1 LSB (RMS over codes; mismatch-type DNL does not
% accumulate -> see dtc_inl_table)
ok13 = true;
for rep = 1:3
    [tbl13, inl13, dnl13] = dtc_inl_table(2^10, cfg0.dtc_inl_lsb, cfg0.dtc_dnl_lsb, 64);
    if abs(inl13-cfg0.dtc_inl_lsb) > 0.1*cfg0.dtc_inl_lsb || ...
       abs(dnl13-cfg0.dtc_dnl_lsb) > 0.05*cfg0.dtc_dnl_lsb
        ok13 = false;
        fprintf('   INL %.3f LSB, DNL %.3f LSB (target %.1f / %.1f)\n', ...
            inl13, dnl13, cfg0.dtc_inl_lsb, cfg0.dtc_dnl_lsb);
    end
end
fprintf('   realized (3 draws): INL ~%.2f LSB RMS, DNL ~%.2f LSB RMS\n', inl13, dnl13);
pr('13. DTC INL/DNL table (INL 2 LSB, DNL 1 LSB, non-accumulating)', ok13);
if ~ok13, n_fail=n_fail+1; end

%% ---- 14. DTC PN-floor spec -> edge jitter conversion --------------------------
% -160 dBc/Hz at fout = 100 MHz, sampled at fref = 100 MHz:
%   sigma_phi = sqrt(2e-16 * fref/2) = 1e-4 rad -> sigma_t = 159.2 fs
s14 = dtc_pn_sigma(-160, 100e6, 100e6);
exp14 = sqrt(2*10^(-16)*100e6/2)/(2*pi*100e6);
ok14 = abs(s14-exp14) < 1e-18 && abs(s14*1e15-159.2) < 1.0;
fprintf('   sigma_t = %.2f fs (formula %.2f fs)\n', s14*1e15, exp14*1e15);
pr('14. DTC PN floor -160 dBc/Hz @100 MHz -> 159 fs RMS jitter', ok14);
if ~ok14, n_fail=n_fail+1; end

%% ----------------------------------------------------------------------------
if n_fail==0
    fprintf('\nCHECK_UNITS: ALL PASS\n');
else
    fprintf('\nCHECK_UNITS: %d FAILURE(S)\n', n_fail);
end

function pr(name,ok)
if ok, fprintf('[PASS] %s\n', name); else, fprintf('[FAIL] %s\n', name); end
end
