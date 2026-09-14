function [freq_div_ratio,psel,eq,dsm_out,frac,sum,carry,S] = dsm_modified_i(rstn_dsm_fb,ref_calib_comp,lfsr_pn10,S,cfg)
% dsm_modified_i — instance-safe version of funcs/dsm_modified.m.
%   The persistent `accum` and the sub-DSM states (dsm_mash / dsm_mash_1bit /
%   modulo2_acc) are carried in the struct S so the feedback DSM and the DCO
%   DSM can run side by side in one session (the golden dsm_mash has shared
%   persistent accumulators and no reset at all).
%
%   S fields: accum, Sdsm (dsm_mash state), Sd1 (dsm_mash_1bit state),
%             Sm2 (modulo2_acc state).  Pass [] to cold-start.
%   Reset behaviour is copied exactly from the original: while rstn_dsm_fb==0
%   the outputs are the static ratio and the internal states are FROZEN.

if isempty(S)
    S = struct('accum',0, ...
               'Sdsm',struct('U1',0,'U2',0,'U3',0,'C2_ff1',0,'C3_ff1',0,'C3_ff2',0), ...
               'Sd1',struct('U1',0), ...
               'Sm2',struct('accum',0));
end
accum = S.accum;

if cfg.near_integer_mode==1
    prbs = lfsr_pn10;
    dither = 0.5*prbs;
    [sum,carry,S.Sm2] = modulo2_acc_i(prbs,S.Sm2,1);
else
    dither = 0;
    sum = 0;
    carry = 0;
end

fcw = cfg.fcw + ref_calib_comp - dither;
% -------------------------------------------------------------------------
% clk_ref时钟域计算
frac = fcw - floor(fcw);
frac = floor(frac*2^cfg.fcw_frac_width)/2^cfg.fcw_frac_width;
% 判断小数是否大于等于0.5
if frac*2>=1
    ovflow = 1;
else
    ovflow = 0;
end
if cfg.sel_clk_fb_en==1
    frac = mod(frac*2,1);
end
fcw_int = floor(fcw);
fcw_int = sat(fcw_int,cfg.fcw_int_width,0);
% clk_mmd时钟域
if rstn_dsm_fb == 1
    [dsm_out,~,S.Sdsm] = dsm_mash_i(frac,cfg.fcw_frac_width,cfg.dsm_fb_mode+1,cfg.dsm_fb_dither,lfsr_pn10,S.Sdsm,1);
    if cfg.dsm_fb_en==0
        dsm_out = 0;
    end
    div_int = floor((dsm_out+ovflow)/2);
    div_frac = (dsm_out+ovflow)/2 - div_int;
    % Modified DSM
    if cfg.sel_clk_fb_en==1
        [ndiv,psel,S.Sd1] = dsm_mash_1bit_i(div_frac,S.Sd1,1);
        freq_div_ratio = fcw_int + div_int + ndiv;
    else
        psel = 0;
        freq_div_ratio = fcw_int + dsm_out;
    end
    % 近正整数模式
    if cfg.near_integer_mode==1
        psel = sum;
        freq_div_ratio = freq_div_ratio + carry;
    end
    % LMT
    if freq_div_ratio<4
        freq_div_ratio = 4;
    end
    if freq_div_ratio>8191
        freq_div_ratio = 8191;
    end
    % 积分之前的相位
    err = dsm_out - frac;
    % DSM输出积分器
    acc_out = accum + err;
    % 减半
    if cfg.sel_clk_fb_en==1
        eq = floor(accum*2^cfg.fcw_frac_width/2)/2^cfg.fcw_frac_width;
    else
        eq = accum;
    end

    % reg uodate
    S.accum = acc_out;
else
    freq_div_ratio = fcw_int;
    psel = 0;
    eq = 0;
    dsm_out = 0;
end

end
