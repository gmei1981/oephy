function dither = lfsr_pn23()

persistent lfsr_reg

if isempty(lfsr_reg)
    lfsr_reg = ones(1,23);
end

feedback = xor(lfsr_reg(23),lfsr_reg(18));
dither = lfsr_reg(23);
% reg update
lfsr_reg = [feedback lfsr_reg(1:22)];

end

