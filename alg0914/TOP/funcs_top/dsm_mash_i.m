function [dsm_out,q_err,S] = dsm_mash_i(frac,frac_width,taps,dither_on,lfsr_pn10,S,rstn)
% dsm_mash_i — instance-safe version of funcs/dsm_mash.m (MASH 1-1-1).
%   Identical arithmetic to the golden model, but the accumulator state is
%   passed in/out through the struct S instead of persistent variables, so
%   several independent DSM instances (dsm_fb 35-bit, dsm_dco 26-bit, ...)
%   can coexist in one Matlab session.  Adds an optional synchronous reset
%   (the original has none — see RM/dsm_dco_rm.m which loads but never uses
%   IND_rstn_dsm_dco).
%
%   S fields: U1,U2,U3,C2_ff1,C3_ff1,C3_ff2  (pass [] to cold-start at 0)
%   rstn: 0 -> state zeroed BEFORE this call's update (reset dominates).

if isempty(S)
    S = struct('U1',0,'U2',0,'U3',0,'C2_ff1',0,'C3_ff1',0,'C3_ff2',0);
end
if rstn==0
    S.U1 = 0; S.U2 = 0; S.U3 = 0;
    S.C2_ff1 = 0; S.C3_ff1 = 0; S.C3_ff2 = 0;
end

U1 = S.U1; U2 = S.U2; U3 = S.U3;
C2_ff1 = S.C2_ff1; C3_ff1 = S.C3_ff1; C3_ff2 = S.C3_ff2;

fractionInternal=2^frac_width*frac;
accumulatorSize=2^frac_width;
% 注入dither
if dither_on==1
    dither = lfsr_pn10;
    high_bits = fractionInternal-mod(fractionInternal,2);
    orig_lsb = mod(fractionInternal,2);
    new_lsb = xor(orig_lsb,dither);
    fractionInternal = high_bits+new_lsb;
end
accum1 = U1+fractionInternal;
accum2 = U1 + U2;
accum3 = U2 + U3;
if accum1>=accumulatorSize
    C1 = 1; %carry 1
    accum1 = accum1 - accumulatorSize;
else
    C1 = 0; %carry 1
end
if accum2>=accumulatorSize
    C2 = 1; %carry 1
    accum2 = accum2 - accumulatorSize;
else
    C2 = 0; %carry 1
end
if accum3>=accumulatorSize
    C3 = 1; %carry 1
    accum3 = accum3 - accumulatorSize;
else
    C3 = 0; %carry 1
end

Yout1 = C1;
Yout2 = C1 + C2 - C2_ff1;
Yout3 = C1 + C2 - C2_ff1 + C3 -2*C3_ff1 + C3_ff2;
% DSM阶数选择
if taps==1
    dsm_out = Yout1;
    q_err = accum1/2^frac_width;
elseif taps==2
    dsm_out = Yout2;
    q_err = accum2/2^frac_width;
elseif taps==3
    dsm_out = Yout3;
    q_err = accum3/2^frac_width;
else
    dsm_out = Yout1;
    q_err = accum1/2^frac_width;
end

% reg update
S.U1 = accum1;
S.U2 = accum2;
S.U3 = accum3;
S.C2_ff1 = C2;
S.C3_ff2 = C3_ff1;
S.C3_ff1 = C3;

end
