function dither = lfsr_pn10()

persistent lfsr_reg

if isempty(lfsr_reg)
    lfsr_reg = ones(1,10);
end

feedback = xor(lfsr_reg(10),lfsr_reg(3));
dither = lfsr_reg(10);
% reg update
lfsr_reg = [feedback lfsr_reg(1:9)];

end

