function M = metrics_calc(L,cfg,calc_cnt)
% metrics_calc — closed-loop performance metrics from the run log L.
%   Physical-DCO version: frequencies come from L.f_dco (Hz).
%   Spec references: lock time 200 us, integrated RMS jitter 200 fs,
%   DCO step 50 kHz, frequency accuracy 1 ppt.

fcw = cfg.adpll_fcw/2^35;
fref = cfg.fref;
Tdco = 1/(fcw*fref);
frac = fcw - floor(fcw);
N = length(L.phe_q);
tail = floor(0.8*N):N;                 % steady-state window (last 20%)

% ---- AFC -------------------------------------------------------------------
idx_afc = find(L.afc_finish==1,1);
if isempty(idx_afc), M.afc_finish_time_us = NaN; else, M.afc_finish_time_us = (idx_afc-1)/fref*1e6; end
M.pbank_final = L.pbank(end);

% ---- FLL -------------------------------------------------------------------
idx_fl = find(L.freq_lock==1,1);
if isempty(idx_fl), M.fll_lock_time_us = NaN; else, M.fll_lock_time_us = (idx_fl-1)/fref*1e6; end
M.freq_ctrl_final = L.freq_ctrl_q(end);
M.fll_freq_err_final = L.fll_err(end);
M.calc_cnt = calc_cnt;
M.abank_final = mean(L.abank(tail));

% ---- lock time -------------------------------------------------------------
pl = L.phase_lock;
lock_idx = NaN;
for k=1:N
    if pl(k)==1 && all(pl(k:end)==1)
        lock_idx = k; break;
    end
end
M.lock_idx = lock_idx;
if isnan(lock_idx)
    M.lock_time_us = NaN;
    M.locked = false;
else
    M.lock_time_us = (lock_idx-1)/fref*1e6;
    M.locked = true;
end

% ---- steady-state phase / frequency ---------------------------------------
M.phe_rms_fs   = std(L.phe_q(tail))*Tdco*1e15;
M.phe_rms_cyc  = std(L.phe_q(tail));
M.freq_err_hz  = mean(L.f_dco(tail)) - fcw*fref;
M.freq_err_ppm = M.freq_err_hz/(fcw*fref)*1e6;

% ---- DTC gain calibration --------------------------------------------------
M.kdtc_final   = mean(L.kdtc(tail));
M.kdtc_target  = 1/cfg.dtc_lsb_cycles;
M.kdtc_err_pct = (M.kdtc_final - M.kdtc_target)/M.kdtc_target*100;
M.g2_final     = mean(L.g2(tail));
M.g2_target    = -cfg.dtc_inl2_a;

% ---- fractional spurs (band power at frac*fref and its 2nd harmonic) ------
M.spur_rms_cyc = NaN;  M.spur_dbc     = NaN;
M.spur2_rms_cyc = NaN; M.spur2_dbc    = NaN;
if M.locked                     % spur level is meaningless when not phase-locked
    phe_ss = L.phe_q(floor(N/2):end);
    phe_ss = phe_ss - mean(phe_ss);
    n = length(phe_ss);
    w = hann_local(n);
    X = fft(phe_ss(:).*w);
    Xr = fft(phe_ss(:));                       % rectangular: for the Nyquist bin
    df = fref/n;
    [M.spur_rms_cyc, M.spur_dbc]      = spur_at(X, w, df, frac*fref, Xr);
    [M.spur2_rms_cyc, M.spur2_dbc]    = spur_at(X, w, df, 2*frac*fref, Xr);
end
end

function [rms_cyc, dbc] = spur_at(X, w, df, fspur, Xr)
% tone band-power at fspur.  A spur exactly at fs/2 (e.g. the 2nd harmonic of
% frac=0.25) sits on the Nyquist bin where the Hann weight vanishes — measured
% from the rectangular-window FFT bin instead.
rms_cyc = NaN; dbc = NaN;
n = length(Xr);
n2 = floor(n/2);
fs2 = n2*df;                                  % nominal Nyquist
if fspur > 3*df && fspur < (n2+3)*df
    if abs(fspur - fs2) < df
        if mod(n,2)==0
            a = abs(Xr(n2+1))*2/n;            % full amplitude of the Nyquist tone
        else                                  % odd n: fs/2 falls between two bins
            k1 = (n-1)/2; k2 = (n+1)/2;
            a = sqrt(abs(Xr(k1+1))^2 + abs(Xr(k2+1))^2)*2/n;
        end
        rms_cyc = a/2;
    else
        k0 = round(fspur/df);
        pbin = mean(abs(X(max(k0-2,1):k0+2)).^2) / (sum(w)^2/4);
        rms_cyc = sqrt(max(pbin,0)/2);
    end
    if rms_cyc > 0
        dbc = 20*log10(2*pi*rms_cyc);
    end
end
end

function w = hann_local(n)
w = 0.5 - 0.5*cos(2*pi*(0:n-1)'/(n-1));
end
