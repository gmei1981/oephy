function [ndiv,psel] = dsm_mash_1bit(frac)

persistent U1       %output of the 1st accum

if isempty(U1)
    U1 = 0;
end

frac_width = 1;
fractionInternal=2^frac_width*frac;
accumulatorSize=2^frac_width;

accum1 = U1+fractionInternal;
if accum1>=accumulatorSize
    C1 = 1; %carry 1
    accum1 = accum1 - accumulatorSize;
else
    C1 = 0; %carry 1
end

ndiv = C1;
psel = U1;

% reg update
U1 = accum1;

end



