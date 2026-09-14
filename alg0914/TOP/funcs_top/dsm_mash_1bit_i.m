function [ndiv,psel,S] = dsm_mash_1bit_i(frac,S,rstn)
% dsm_mash_1bit_i — instance-safe version of funcs/dsm_mash_1bit.m.
%   1-bit accumulator used by dsm_modified when sel_clk_fb_en=1.

if isempty(S)
    S = struct('U1',0);
end
if rstn==0
    S.U1 = 0;
end

frac_width = 1;
fractionInternal=2^frac_width*frac;
accumulatorSize=2^frac_width;

accum1 = S.U1+fractionInternal;
if accum1>=accumulatorSize
    C1 = 1; %carry 1
    accum1 = accum1 - accumulatorSize;
else
    C1 = 0; %carry 1
end

ndiv = C1;
psel = S.U1;

% reg update
S.U1 = accum1;

end
