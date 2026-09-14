function dsm_code = therm_dco_code(dsm_out,taps)
% therm_dco_code — MASH output -> DCO fine-bank thermometer code.
%   Exact copy of the transcoding in RM/dsm_dco_rm.m.
%   taps==1: dsm_out(0/1)          -> code 0..1   (midscale 0)
%   taps==2: dsm_out(-1..2)        -> code 0..3   (midscale 1)
%   taps==3: dsm_out(-3..4)        -> code 0..7   (midscale 3; code = dsm_out+3)

if taps==1
    dsm_code = dsm_out;
elseif taps==2
    if dsm_out<0
        dsm_code = 0;
    else
        bit0 = bitget(dsm_out,1);
        bit1 = bitget(dsm_out,2);
        dsm_code = ~bit0 + 2*xor(bit0,bit1);
    end
elseif taps==3
    if dsm_out<0
        dsm_out_com = dsm_out + 2^4;
    else
        dsm_out_com = dsm_out + 0;
    end
    bit0 = bitget(dsm_out_com,1);
    bit1 = bitget(dsm_out_com,2);
    bit2 = bitget(dsm_out_com,3);
    dsm_code = ~bit0 + 2*(~xor(bit0,bit1)) + 4*xor(bit2,or(bit0,bit1));
else
    error('taps must be 1/2/3');
end
end
