function pn = gen_lfsr_pn10(n,seed_state)
% gen_lfsr_pn10 — precompute the PN10 dither stream of funcs/lfsr_pn10.m.
%   Identical recurrence (taps x^10+x^3:  feedback = xor(reg(10),reg(3)),
%   output = reg(10), shift-left, initial register all ones) but returned as
%   a deterministic vector so every consumer samples the same stream without
%   sharing persistent state.

if nargin<2 || isempty(seed_state)
    seed_state = ones(1,10);
end
lfsr_reg = seed_state;
pn = zeros(n,1);
for k=1:n
    feedback = xor(lfsr_reg(10),lfsr_reg(3));
    pn(k) = lfsr_reg(10);
    lfsr_reg = [feedback lfsr_reg(1:9)];
end
end
