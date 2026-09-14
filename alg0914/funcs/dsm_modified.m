function [freq_div_ratio,psel,eq,dsm_out,frac,sum,carry] = dsm_modified(rstn_dsm_fb,ref_calib_comp,lfsr_pn10,cfg)

persistent accum
persistent time

if isempty(accum)
    accum = 0;
    time = 0;
end

time = time + 1;

% if time==5000
%     prbs = 1;
% elseif time==5003
%     prbs = 1;
% else
%     prbs = 0;
% end

if cfg.near_integer_mode==1
    % prbs = randi([0,1]);
    prbs = lfsr_pn10;
    dither = 0.5*prbs;
    [sum,carry] = modulo2_acc(prbs);
else
    dither = 0;
    sum = 0;
    carry = 0;
end

cfg.fcw = cfg.fcw + ref_calib_comp - dither;
% -------------------------------------------------------------------------
% clk_ref时钟域计算
frac = cfg.fcw - floor(cfg.fcw);
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
fcw_int = floor(cfg.fcw);
fcw_int = sat(fcw_int,cfg.fcw_int_width,0);
% clk_mmd时钟域
if rstn_dsm_fb == 1
    [dsm_out,~] = dsm_mash(frac,cfg.fcw_frac_width,cfg.dsm_fb_mode+1,cfg.dsm_fb_dither,lfsr_pn10);
    if cfg.dsm_fb_en==0
        dsm_out = 0;
    end
    div_int = floor((dsm_out+ovflow)/2);
    div_frac = (dsm_out+ovflow)/2 - div_int;
    % Modified DSM
    if cfg.sel_clk_fb_en==1
        [ndiv,psel] = dsm_mash_1bit(div_frac);
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
    accum = acc_out;
else
    freq_div_ratio = fcw_int;
    psel = 0;
    eq = 0;
    dsm_out = 0;
end

% reg update



