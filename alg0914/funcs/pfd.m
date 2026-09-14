function [phe_out,ctdc_in_one_hot_a,ctdc_in_one_hot_b] = pfd(arb_out,ctdc_out_a,ctdc_out_b,ftdc_out,cfg)

if cfg.phe_inv_en == 1
    if arb_out==1
        decoder_out_sign = 0;
    else
        decoder_out_sign = 1;
    end
else
    decoder_out_sign = arb_out;
end
% 解码
if ctdc_out_a==0
    decoder_out_a = 0;
elseif ctdc_out_a==2^15
    decoder_out_a = 1; 
elseif ctdc_out_a==2^15+2^14
    decoder_out_a = 2; 
elseif ctdc_out_a==2^15+2^14+2^13
    decoder_out_a = 3; 
elseif ctdc_out_a==2^15+2^14+2^13+2^12
    decoder_out_a = 4; 
elseif ctdc_out_a==2^15+2^14+2^13+2^12+2^11
    decoder_out_a = 5;     
elseif ctdc_out_a==2^15+2^14+2^13+2^12+2^11+2^10
    decoder_out_a = 6; 
elseif ctdc_out_a==2^15+2^14+2^13+2^12+2^11+2^10+2^9
    decoder_out_a = 7; 
elseif ctdc_out_a==2^15+2^14+2^13+2^12+2^11+2^10+2^9+2^8
    decoder_out_a = 8; 
elseif ctdc_out_a==2^15+2^14+2^13+2^12+2^11+2^10+2^9+2^8+2^7
    decoder_out_a = 9; 
elseif ctdc_out_a==2^15+2^14+2^13+2^12+2^11+2^10+2^9+2^8+2^7+2^6
    decoder_out_a = 10; 
elseif ctdc_out_a==2^15+2^14+2^13+2^12+2^11+2^10+2^9+2^8+2^7+2^6+2^5
    decoder_out_a = 11; 
elseif ctdc_out_a==2^15+2^14+2^13+2^12+2^11+2^10+2^9+2^8+2^7+2^6+2^5+2^4
    decoder_out_a = 12; 
elseif ctdc_out_a==2^15+2^14+2^13+2^12+2^11+2^10+2^9+2^8+2^7+2^6+2^5+2^4+2^3
    decoder_out_a = 13; 
elseif ctdc_out_a==2^15+2^14+2^13+2^12+2^11+2^10+2^9+2^8+2^7+2^6+2^5+2^4+2^3+2^2
    decoder_out_a = 14; 
elseif ctdc_out_a==2^15+2^14+2^13+2^12+2^11+2^10+2^9+2^8+2^7+2^6+2^5+2^4+2^3+2^2+2^1
    decoder_out_a = 15; 
else
    decoder_out_a = 0;
end

% 解码
if ctdc_out_b==0
    decoder_out_b = 0;
elseif ctdc_out_b==2^15
    decoder_out_b = 1; 
elseif ctdc_out_b==2^15+2^14
    decoder_out_b = 2; 
elseif ctdc_out_b==2^15+2^14+2^13
    decoder_out_b = 3; 
elseif ctdc_out_b==2^15+2^14+2^13+2^12
    decoder_out_b = 4; 
elseif ctdc_out_b==2^15+2^14+2^13+2^12+2^11
    decoder_out_b = 5;     
elseif ctdc_out_b==2^15+2^14+2^13+2^12+2^11+2^10
    decoder_out_b = 6; 
elseif ctdc_out_b==2^15+2^14+2^13+2^12+2^11+2^10+2^9
    decoder_out_b = 7; 
elseif ctdc_out_b==2^15+2^14+2^13+2^12+2^11+2^10+2^9+2^8
    decoder_out_b = 8; 
elseif ctdc_out_b==2^15+2^14+2^13+2^12+2^11+2^10+2^9+2^8+2^7
    decoder_out_b = 9; 
elseif ctdc_out_b==2^15+2^14+2^13+2^12+2^11+2^10+2^9+2^8+2^7+2^6
    decoder_out_b = 10; 
elseif ctdc_out_b==2^15+2^14+2^13+2^12+2^11+2^10+2^9+2^8+2^7+2^6+2^5
    decoder_out_b = 11; 
elseif ctdc_out_b==2^15+2^14+2^13+2^12+2^11+2^10+2^9+2^8+2^7+2^6+2^5+2^4
    decoder_out_b = 12; 
elseif ctdc_out_b==2^15+2^14+2^13+2^12+2^11+2^10+2^9+2^8+2^7+2^6+2^5+2^4+2^3
    decoder_out_b = 13; 
elseif ctdc_out_b==2^15+2^14+2^13+2^12+2^11+2^10+2^9+2^8+2^7+2^6+2^5+2^4+2^3+2^2
    decoder_out_b = 14; 
elseif ctdc_out_b==2^15+2^14+2^13+2^12+2^11+2^10+2^9+2^8+2^7+2^6+2^5+2^4+2^3+2^2+2^1
    decoder_out_b = 15; 
else
    decoder_out_b = 0;  
end
% 解码
if ftdc_out==0
    decoder_out_low = 0;
elseif ftdc_out==2^15
    decoder_out_low = 1; 
elseif ftdc_out==2^15+2^14
    decoder_out_low = 2; 
elseif ftdc_out==2^15+2^14+2^13
    decoder_out_low = 3; 
elseif ftdc_out==2^15+2^14+2^13+2^12
    decoder_out_low = 4; 
elseif ftdc_out==2^15+2^14+2^13+2^12+2^11
    decoder_out_low = 5;     
elseif ftdc_out==2^15+2^14+2^13+2^12+2^11+2^10
    decoder_out_low = 6; 
elseif ftdc_out==2^15+2^14+2^13+2^12+2^11+2^10+2^9
    decoder_out_low = 7; 
elseif ftdc_out==2^15+2^14+2^13+2^12+2^11+2^10+2^9+2^8
    decoder_out_low = 8; 
elseif ftdc_out==2^15+2^14+2^13+2^12+2^11+2^10+2^9+2^8+2^7
    decoder_out_low = 9; 
elseif ftdc_out==2^15+2^14+2^13+2^12+2^11+2^10+2^9+2^8+2^7+2^6
    decoder_out_low = 10; 
elseif ftdc_out==2^15+2^14+2^13+2^12+2^11+2^10+2^9+2^8+2^7+2^6+2^5
    decoder_out_low = 11; 
elseif ftdc_out==2^15+2^14+2^13+2^12+2^11+2^10+2^9+2^8+2^7+2^6+2^5+2^4
    decoder_out_low = 12; 
elseif ftdc_out==2^15+2^14+2^13+2^12+2^11+2^10+2^9+2^8+2^7+2^6+2^5+2^4+2^3
    decoder_out_low = 13; 
elseif ftdc_out==2^15+2^14+2^13+2^12+2^11+2^10+2^9+2^8+2^7+2^6+2^5+2^4+2^3+2^2
    decoder_out_low = 14; 
elseif ftdc_out==2^15+2^14+2^13+2^12+2^11+2^10+2^9+2^8+2^7+2^6+2^5+2^4+2^3+2^2+2^1
    decoder_out_low = 15; 
else
    decoder_out_low = 0;
end

if arb_out==1
    decoder_out_high = decoder_out_a;
else
    decoder_out_high = decoder_out_b;
end

if decoder_out_sign==0
    tdc_code = decoder_out_high*2^4+decoder_out_low;
else
    tdc_code = -1*(decoder_out_high*2^4+decoder_out_low);
end

if decoder_out_high~=0
    if decoder_out_sign==1
        tdc_code = tdc_code + 16;
    else
        tdc_code = tdc_code - 16;
    end
end

tdc_phe = tdc_code*cfg.tdc_norm_coef;
phe = sat(tdc_phe,2,1);
phe_out = phe + cfg.phe_sh;
% 解热码
if bitget(ctdc_out_a,17)==0
    ctdc_in_one_hot_a = 2^15;
elseif bitget(ctdc_out_a,17)==1 && bitget(ctdc_out_a,16)==0
    ctdc_in_one_hot_a = 2^15;
elseif bitget(ctdc_out_a,17)==1 && bitget(ctdc_out_a,16)==1 && bitget(ctdc_out_a,15)==0
    ctdc_in_one_hot_a = 2^14;
elseif bitget(ctdc_out_a,17)==1 && bitget(ctdc_out_a,16)==1 && bitget(ctdc_out_a,15)==1 && bitget(ctdc_out_a,14)==0
    ctdc_in_one_hot_a = 2^13;
elseif bitget(ctdc_out_a,17)==1 && bitget(ctdc_out_a,16)==1 && bitget(ctdc_out_a,15)==1 && bitget(ctdc_out_a,14)==1 && bitget(ctdc_out_a,13)==0
    ctdc_in_one_hot_a = 2^12;
elseif bitget(ctdc_out_a,17)==1 && bitget(ctdc_out_a,16)==1 && bitget(ctdc_out_a,15)==1 && bitget(ctdc_out_a,14)==1 && bitget(ctdc_out_a,13)==1 && bitget(ctdc_out_a,12)==0
    ctdc_in_one_hot_a = 2^11;
elseif bitget(ctdc_out_a,17)==1 && bitget(ctdc_out_a,16)==1 && bitget(ctdc_out_a,15)==1 && bitget(ctdc_out_a,14)==1 && bitget(ctdc_out_a,13)==1 && bitget(ctdc_out_a,12)==1 && bitget(ctdc_out_a,11)==0
    ctdc_in_one_hot_a = 2^10;
elseif bitget(ctdc_out_a,17)==1 && bitget(ctdc_out_a,16)==1 && bitget(ctdc_out_a,15)==1 && bitget(ctdc_out_a,14)==1 && bitget(ctdc_out_a,13)==1 && bitget(ctdc_out_a,12)==1 && bitget(ctdc_out_a,11)==1 && bitget(ctdc_out_a,10)==0
    ctdc_in_one_hot_a = 2^9;
elseif bitget(ctdc_out_a,17)==1 && bitget(ctdc_out_a,16)==1 && bitget(ctdc_out_a,15)==1 && bitget(ctdc_out_a,14)==1 && bitget(ctdc_out_a,13)==1 && bitget(ctdc_out_a,12)==1 && bitget(ctdc_out_a,11)==1 && bitget(ctdc_out_a,10)==1 && bitget(ctdc_out_a,9)==0
    ctdc_in_one_hot_a = 2^8;
elseif bitget(ctdc_out_a,17)==1 && bitget(ctdc_out_a,16)==1 && bitget(ctdc_out_a,15)==1 && bitget(ctdc_out_a,14)==1 && bitget(ctdc_out_a,13)==1 && bitget(ctdc_out_a,12)==1 && bitget(ctdc_out_a,11)==1 && bitget(ctdc_out_a,10)==1 && bitget(ctdc_out_a,9)==1 && bitget(ctdc_out_a,8)==0 
    ctdc_in_one_hot_a = 2^7;
elseif bitget(ctdc_out_a,17)==1 && bitget(ctdc_out_a,16)==1 && bitget(ctdc_out_a,15)==1 && bitget(ctdc_out_a,14)==1 && bitget(ctdc_out_a,13)==1 && bitget(ctdc_out_a,12)==1 && bitget(ctdc_out_a,11)==1 && bitget(ctdc_out_a,10)==1 && bitget(ctdc_out_a,9)==1 && bitget(ctdc_out_a,8)==1 && bitget(ctdc_out_a,7)==0 
    ctdc_in_one_hot_a = 2^6;
elseif bitget(ctdc_out_a,17)==1 && bitget(ctdc_out_a,16)==1 && bitget(ctdc_out_a,15)==1 && bitget(ctdc_out_a,14)==1 && bitget(ctdc_out_a,13)==1 && bitget(ctdc_out_a,12)==1 && bitget(ctdc_out_a,11)==1 && bitget(ctdc_out_a,10)==1 && bitget(ctdc_out_a,9)==1 && bitget(ctdc_out_a,8)==1 && bitget(ctdc_out_a,7)==1 && bitget(ctdc_out_a,6)==0 
    ctdc_in_one_hot_a = 2^6;
elseif bitget(ctdc_out_a,17)==1 && bitget(ctdc_out_a,16)==1 && bitget(ctdc_out_a,15)==1 && bitget(ctdc_out_a,14)==1 && bitget(ctdc_out_a,13)==1 && bitget(ctdc_out_a,12)==1 && bitget(ctdc_out_a,11)==1 && bitget(ctdc_out_a,10)==1 && bitget(ctdc_out_a,9)==1 && bitget(ctdc_out_a,8)==1 && bitget(ctdc_out_a,7)==1 && bitget(ctdc_out_a,6)==1 && bitget(ctdc_out_a,5)==0 
    ctdc_in_one_hot_a = 2^4;
elseif bitget(ctdc_out_a,17)==1 && bitget(ctdc_out_a,16)==1 && bitget(ctdc_out_a,15)==1 && bitget(ctdc_out_a,14)==1 && bitget(ctdc_out_a,13)==1 && bitget(ctdc_out_a,12)==1 && bitget(ctdc_out_a,11)==1 && bitget(ctdc_out_a,10)==1 && bitget(ctdc_out_a,9)==1 && bitget(ctdc_out_a,8)==1 && bitget(ctdc_out_a,7)==1 && bitget(ctdc_out_a,6)==1 && bitget(ctdc_out_a,5)==1 && bitget(ctdc_out_a,4)==0 
    ctdc_in_one_hot_a = 2^3;
elseif bitget(ctdc_out_a,17)==1 && bitget(ctdc_out_a,16)==1 && bitget(ctdc_out_a,15)==1 && bitget(ctdc_out_a,14)==1 && bitget(ctdc_out_a,13)==1 && bitget(ctdc_out_a,12)==1 && bitget(ctdc_out_a,11)==1 && bitget(ctdc_out_a,10)==1 && bitget(ctdc_out_a,9)==1 && bitget(ctdc_out_a,8)==1 && bitget(ctdc_out_a,7)==1 && bitget(ctdc_out_a,6)==1 && bitget(ctdc_out_a,5)==1 && bitget(ctdc_out_a,4)==1 && bitget(ctdc_out_a,3)==0 
    ctdc_in_one_hot_a = 2^2;
elseif bitget(ctdc_out_a,17)==1 && bitget(ctdc_out_a,16)==1 && bitget(ctdc_out_a,15)==1 && bitget(ctdc_out_a,14)==1 && bitget(ctdc_out_a,13)==1 && bitget(ctdc_out_a,12)==1 && bitget(ctdc_out_a,11)==1 && bitget(ctdc_out_a,10)==1 && bitget(ctdc_out_a,9)==1 && bitget(ctdc_out_a,8)==1 && bitget(ctdc_out_a,7)==1 && bitget(ctdc_out_a,6)==1 && bitget(ctdc_out_a,5)==1 && bitget(ctdc_out_a,4)==1 && bitget(ctdc_out_a,3)==1 && bitget(ctdc_out_a,2)==0 
    ctdc_in_one_hot_a = 2^1;
elseif bitget(ctdc_out_a,17)==1 && bitget(ctdc_out_a,16)==1 && bitget(ctdc_out_a,15)==1 && bitget(ctdc_out_a,14)==1 && bitget(ctdc_out_a,13)==1 && bitget(ctdc_out_a,12)==1 && bitget(ctdc_out_a,11)==1 && bitget(ctdc_out_a,10)==1 && bitget(ctdc_out_a,9)==1 && bitget(ctdc_out_a,8)==1 && bitget(ctdc_out_a,7)==1 && bitget(ctdc_out_a,6)==1 && bitget(ctdc_out_a,5)==1 && bitget(ctdc_out_a,4)==1 && bitget(ctdc_out_a,3)==1 && bitget(ctdc_out_a,2)==1 && bitget(ctdc_out_a,1)==0  
    ctdc_in_one_hot_a = 2^0;
else
    ctdc_in_one_hot_a = 0;
end

% 解热码
if bitget(ctdc_out_b,17)==0
    ctdc_in_one_hot_b = 2^15;
elseif bitget(ctdc_out_b,17)==1 && bitget(ctdc_out_b,16)==0
    ctdc_in_one_hot_b = 2^15;
elseif bitget(ctdc_out_b,17)==1 && bitget(ctdc_out_b,16)==1 && bitget(ctdc_out_b,15)==0
    ctdc_in_one_hot_b = 2^14;
elseif bitget(ctdc_out_b,17)==1 && bitget(ctdc_out_b,16)==1 && bitget(ctdc_out_b,15)==1 && bitget(ctdc_out_b,14)==0
    ctdc_in_one_hot_b = 2^13;
elseif bitget(ctdc_out_b,17)==1 && bitget(ctdc_out_b,16)==1 && bitget(ctdc_out_b,15)==1 && bitget(ctdc_out_b,14)==1 && bitget(ctdc_out_b,13)==0
    ctdc_in_one_hot_b = 2^12;
elseif bitget(ctdc_out_b,17)==1 && bitget(ctdc_out_b,16)==1 && bitget(ctdc_out_b,15)==1 && bitget(ctdc_out_b,14)==1 && bitget(ctdc_out_b,13)==1 && bitget(ctdc_out_b,12)==0
    ctdc_in_one_hot_b = 2^11;
elseif bitget(ctdc_out_b,17)==1 && bitget(ctdc_out_b,16)==1 && bitget(ctdc_out_b,15)==1 && bitget(ctdc_out_b,14)==1 && bitget(ctdc_out_b,13)==1 && bitget(ctdc_out_b,12)==1 && bitget(ctdc_out_b,11)==0
    ctdc_in_one_hot_b = 2^10;
elseif bitget(ctdc_out_b,17)==1 && bitget(ctdc_out_b,16)==1 && bitget(ctdc_out_b,15)==1 && bitget(ctdc_out_b,14)==1 && bitget(ctdc_out_b,13)==1 && bitget(ctdc_out_b,12)==1 && bitget(ctdc_out_b,11)==1 && bitget(ctdc_out_b,10)==0
    ctdc_in_one_hot_b = 2^9;
elseif bitget(ctdc_out_b,17)==1 && bitget(ctdc_out_b,16)==1 && bitget(ctdc_out_b,15)==1 && bitget(ctdc_out_b,14)==1 && bitget(ctdc_out_b,13)==1 && bitget(ctdc_out_b,12)==1 && bitget(ctdc_out_b,11)==1 && bitget(ctdc_out_b,10)==1 && bitget(ctdc_out_b,9)==0
    ctdc_in_one_hot_b = 2^8;
elseif bitget(ctdc_out_b,17)==1 && bitget(ctdc_out_b,16)==1 && bitget(ctdc_out_b,15)==1 && bitget(ctdc_out_b,14)==1 && bitget(ctdc_out_b,13)==1 && bitget(ctdc_out_b,12)==1 && bitget(ctdc_out_b,11)==1 && bitget(ctdc_out_b,10)==1 && bitget(ctdc_out_b,9)==1 && bitget(ctdc_out_b,8)==0 
    ctdc_in_one_hot_b = 2^7;
elseif bitget(ctdc_out_b,17)==1 && bitget(ctdc_out_b,16)==1 && bitget(ctdc_out_b,15)==1 && bitget(ctdc_out_b,14)==1 && bitget(ctdc_out_b,13)==1 && bitget(ctdc_out_b,12)==1 && bitget(ctdc_out_b,11)==1 && bitget(ctdc_out_b,10)==1 && bitget(ctdc_out_b,9)==1 && bitget(ctdc_out_b,8)==1 && bitget(ctdc_out_b,7)==0 
    ctdc_in_one_hot_b = 2^6;
elseif bitget(ctdc_out_b,17)==1 && bitget(ctdc_out_b,16)==1 && bitget(ctdc_out_b,15)==1 && bitget(ctdc_out_b,14)==1 && bitget(ctdc_out_b,13)==1 && bitget(ctdc_out_b,12)==1 && bitget(ctdc_out_b,11)==1 && bitget(ctdc_out_b,10)==1 && bitget(ctdc_out_b,9)==1 && bitget(ctdc_out_b,8)==1 && bitget(ctdc_out_b,7)==1 && bitget(ctdc_out_b,6)==0 
    ctdc_in_one_hot_b = 2^6;
elseif bitget(ctdc_out_b,17)==1 && bitget(ctdc_out_b,16)==1 && bitget(ctdc_out_b,15)==1 && bitget(ctdc_out_b,14)==1 && bitget(ctdc_out_b,13)==1 && bitget(ctdc_out_b,12)==1 && bitget(ctdc_out_b,11)==1 && bitget(ctdc_out_b,10)==1 && bitget(ctdc_out_b,9)==1 && bitget(ctdc_out_b,8)==1 && bitget(ctdc_out_b,7)==1 && bitget(ctdc_out_b,6)==1 && bitget(ctdc_out_b,5)==0 
    ctdc_in_one_hot_b = 2^4;
elseif bitget(ctdc_out_b,17)==1 && bitget(ctdc_out_b,16)==1 && bitget(ctdc_out_b,15)==1 && bitget(ctdc_out_b,14)==1 && bitget(ctdc_out_b,13)==1 && bitget(ctdc_out_b,12)==1 && bitget(ctdc_out_b,11)==1 && bitget(ctdc_out_b,10)==1 && bitget(ctdc_out_b,9)==1 && bitget(ctdc_out_b,8)==1 && bitget(ctdc_out_b,7)==1 && bitget(ctdc_out_b,6)==1 && bitget(ctdc_out_b,5)==1 && bitget(ctdc_out_b,4)==0 
    ctdc_in_one_hot_b = 2^3;
elseif bitget(ctdc_out_b,17)==1 && bitget(ctdc_out_b,16)==1 && bitget(ctdc_out_b,15)==1 && bitget(ctdc_out_b,14)==1 && bitget(ctdc_out_b,13)==1 && bitget(ctdc_out_b,12)==1 && bitget(ctdc_out_b,11)==1 && bitget(ctdc_out_b,10)==1 && bitget(ctdc_out_b,9)==1 && bitget(ctdc_out_b,8)==1 && bitget(ctdc_out_b,7)==1 && bitget(ctdc_out_b,6)==1 && bitget(ctdc_out_b,5)==1 && bitget(ctdc_out_b,4)==1 && bitget(ctdc_out_b,3)==0 
    ctdc_in_one_hot_b = 2^2;
elseif bitget(ctdc_out_b,17)==1 && bitget(ctdc_out_b,16)==1 && bitget(ctdc_out_b,15)==1 && bitget(ctdc_out_b,14)==1 && bitget(ctdc_out_b,13)==1 && bitget(ctdc_out_b,12)==1 && bitget(ctdc_out_b,11)==1 && bitget(ctdc_out_b,10)==1 && bitget(ctdc_out_b,9)==1 && bitget(ctdc_out_b,8)==1 && bitget(ctdc_out_b,7)==1 && bitget(ctdc_out_b,6)==1 && bitget(ctdc_out_b,5)==1 && bitget(ctdc_out_b,4)==1 && bitget(ctdc_out_b,3)==1 && bitget(ctdc_out_b,2)==0 
    ctdc_in_one_hot_b = 2^1;
elseif bitget(ctdc_out_b,17)==1 && bitget(ctdc_out_b,16)==1 && bitget(ctdc_out_b,15)==1 && bitget(ctdc_out_b,14)==1 && bitget(ctdc_out_b,13)==1 && bitget(ctdc_out_b,12)==1 && bitget(ctdc_out_b,11)==1 && bitget(ctdc_out_b,10)==1 && bitget(ctdc_out_b,9)==1 && bitget(ctdc_out_b,8)==1 && bitget(ctdc_out_b,7)==1 && bitget(ctdc_out_b,6)==1 && bitget(ctdc_out_b,5)==1 && bitget(ctdc_out_b,4)==1 && bitget(ctdc_out_b,3)==1 && bitget(ctdc_out_b,2)==1 && bitget(ctdc_out_b,1)==0  
    ctdc_in_one_hot_b = 2^0;
else
    ctdc_in_one_hot_b = 0;
end



