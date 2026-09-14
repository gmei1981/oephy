function [P,x,fb_fresh,afc_fresh,f_dco] = plant_update(P,ratio,tau,pbank,fll_en,rstn_fll,afc_en,dco_pn_samp)
% plant_update — one reference cycle of the behavioral "analog" plant:
%   PHYSICAL three-bank DCO, MMD divider edge reconstruction, FLL and AFC
%   feedback counters, and the TDC residual.
%
%   DCO (actual architecture, all constants cfg):
%     pbank (6b) : sub-band select, each code = a 30 MHz band, 15 MHz spacing
%     abank (9b) : 511 sub-steps covering the full 30 MHz band
%                  -> dco_abank_lsb = dco_abank_span/511
%     fbank (3b) : 8 codes = 1 abank LSB (lpf_frac through the SDM, averaged
%                  by the caller into ctrl_eff's fractional part)
%     f_dco = dco_f_lo + pbank*dco_pbank_step + ctrl_eff*dco_abank_lsb*(1+kvco)
%     ctrl_eff = abank + fbank_mean/8   (code units, ~[0,512))
%   Phase advances by f_dco/fref DCO cycles per reference cycle; controls
%   computed in cycle i-1 are active in cycle i (caller sets P.ctrl_prev).
%
%   Divider: fb edge i occurs when the DCO phase reaches
%       tgt(i) = tgt(i-1) + ratio(i)      [DCO cycles]
%   which reproduces the DSM quantization phase exactly:
%       tgt(i) = FCW*i + accum(i)   (accum = dsm_modified's post-update eq).
%
%   TDC residual (sign so that x>0 = ref leads = DCO must speed up):
%       x = tgt - (phi + tau)
%   with tau = DTC delay in DCO cycles (bulk ~1 cycle, dtc_offset).
%
%   FLL counter: rising edges of a DCO/4 prescaler clock, windowed every
%   P.wcnt_max reference cycles (fll.m expects calc_cnt = FCW*W/4 counts).
%   AFC counter: rising edges of DCO/P.afc_div, windowed every P.afc_wmax
%   cycles (expected = FCW/afc_div*2^afc_ref_cnt_thr).  fb_fresh/afc_fresh
%   flag the first cycle after each window boundary (pulse convention).
%
%   P fields: phi, tgt, ctrl_prev, f_dco, wcnt, phi_ws, fb_delta, wcnt_max,
%             awcnt, aphi_ws, afc_delta, afc_wmax, afc_div

if ~isfield(P,'wcnt_max'), error('plant_update: P must be initialized (wcnt_max)'); end

% ---- DCO (previous control active now) --------------------------------------
f_dco = P.f_lo + pbank*P.pstep + P.ctrl_prev*P.alsb;
phi = P.phi + f_dco/P.fref + dco_pn_samp;

% ---- divider edge + TDC residual ------------------------------------------
tgt = P.tgt + ratio;
x = tgt - (phi + tau);

% ---- FLL windowed fb counter (DCO/4 edge count) ---------------------------
fb_fresh = 0;
if rstn_fll==0 || fll_en==0
    P.wcnt = 0;
else
    if P.wcnt==0
        P.phi_ws = P.phi;      % snapshot BEFORE this call's advance: window spans exactly W advances
    end
    P.wcnt = P.wcnt + 1;
    if P.wcnt >= P.wcnt_max
        P.fb_delta = floor(phi/4) - floor(P.phi_ws/4);
        fb_fresh = 1;
        P.wcnt = 0;
    end
end

% ---- AFC windowed fb counter (DCO/afc_div edge count) ----------------------
afc_fresh = 0;
if afc_en==0
    P.awcnt = 0;
else
    if P.awcnt==0
        P.ap_ws = P.phi;       % snapshot BEFORE this call's advance (same W-exact trick)
    end
    P.awcnt = P.awcnt + 1;
    if P.awcnt >= P.afc_wmax
        P.afc_delta = floor(phi/P.afc_div) - floor(P.ap_ws/P.afc_div);
        afc_fresh = 1;
        P.awcnt = 0;
    end
end

% ---- reg update -------------------------------------------------------------
P.phi = phi;
P.tgt = tgt;
P.f_dco = f_dco;
end
