function [arb,ctdc_a,ctdc_b,ftdc] = tdc_encode(x,cfg)
% tdc_encode — behavioral TDC front end for the closed-loop sim.
%
%   Input  x : signed residual  x = tgt_edge - (phi + tau)  in DCO cycles,
%              i.e. how much the divider edge LAGS the DTC-delayed reference
%              edge.  x>0  =>  reference leads  =>  oscillator slow
%              =>  phe_out must be positive so the loop speeds the DCO up.
%              (Sign convention verified against rtl/adpll/pfd/pfd.v:
%              arb_out=1 means "ref leads".)
%
%   The TDC measures phase modulo one DCO cycle: x is wrapped into
%   [-0.5,0.5) cycles, quantized to 1/256-cycle LSB (tdc_norm_coef = 2^-8)
%   and split into a coarse (CTDC, 4b) and a fine (FTDC, 4b) nibble:
%       v    = |x_wrap|*256  in [0,128)   (TDC linear range is +-239 LSB)
%       high = floor(v/16)+1 in [1,15]    (coarse, one-hot bank A or B)
%       low  = v mod 16       in [0,15]   (fine, one-hot)
%   The magnitude code goes into the bank selected by arb (A if ref leads,
%   else B); the other bank outputs 0 (dead zone) exactly as the analog
%   front end would.  funcs/pfd.m decodes this back to  +-v*2^-8  —
%   verified round-trip for every v in 0..239 (check_units.m).
%
%   cfg.tdc_noise_lsb : additive Gaussian noise on v in LSB (default 0)

if ~isfield(cfg,'tdc_noise_lsb'), cfg.tdc_noise_lsb = 0; end

xm = x - round(x);                    % mod-1 wrap into [-0.5,0.5)
v = abs(xm)*256;
if cfg.tdc_noise_lsb > 0
    v = v + cfg.tdc_noise_lsb*randn;
end
% static INL of the delay-cell chain (transfer-curve deviation in LSB):
% v_measured = v_ideal + INL(v_ideal), table indexed by the ideal code
if isfield(cfg,'tdc_inl_vec') && ~isempty(cfg.tdc_inl_vec)
    idx = floor(min(max(v,0),255)) + 1;
    v = v + cfg.tdc_inl_vec(idx);
end
v = min(max(round(v),0),239);         % TDC full scale

arb = double(xm >= 0);                % 1 = ref leads
high = floor(v/16) + 1;               % 1..15
low  = v - 16*floor(v/16);            % 0..15

onehot_high = onehot_enc(high);
ftdc = onehot_enc(low);
if arb==1
    ctdc_a = onehot_high;
    ctdc_b = 0;
else
    ctdc_a = 0;
    ctdc_b = onehot_high;
end
end

function code = onehot_enc(n)
% onehot_enc — the exact thermometer patterns funcs/pfd.m decodes:
%   n=0 -> 0 (dead zone);  n>=1 -> bits 15..(16-n) set = 2^16 - 2^(16-n)
if n<=0
    code = 0;
else
    code = 2^16 - 2^(16-n);
end
end
