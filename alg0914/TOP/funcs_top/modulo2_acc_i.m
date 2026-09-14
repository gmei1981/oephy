function [sum,carry,S] = modulo2_acc_i(prbs,S,rstn)
% modulo2_acc_i — instance-safe version of funcs/modulo2_acc.m.
%   mod-2 accumulator for the near-integer-mode psel/carry path of
%   dsm_modified.

if isempty(S)
    S = struct('accum',0);
end
if rstn==0
    S.accum = 0;
end

accum1 = S.accum + prbs;
if accum1>=2
    carry = 1;
    accum1 = accum1 - 2;
else
    carry = 0;
end
sum = S.accum;

% reg upodate
S.accum = accum1;

end
