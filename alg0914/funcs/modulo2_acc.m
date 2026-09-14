function [sum,carry] = modulo2_acc(prbs)

persistent accum

if isempty(accum)
    accum = 0;
end

accum1 = accum + prbs;
if accum1>=2
    carry = 1; 
    accum1 = accum1 - 2;
else
    carry = 0; 
end
sum = accum;

% reg upodate
accum = accum1;

end

