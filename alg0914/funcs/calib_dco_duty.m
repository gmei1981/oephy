function [dco_calib_coef,phe_sign,dco_dtc_comp] = calib_dco_duty(dco_start,rstn_calib,phe,sel_clk_fb,cfg)


persistent integ
persistent sel_clk_fb_ff
persistent dco_start_cnt

if isempty(integ)
    integ = 0;
    sel_clk_fb_ff = 0;
    dco_start_cnt = 0;
end

% 启动延时
if rstn_calib==1
    if dco_start==1
        dco_start_en = 1;
    else
        dco_start_en = 0;
    end
else
    dco_start_en = 0;
end

% 校准使能
if cfg.dco_duty_calib_en==1 && dco_start_en==1
    phe_sign = sign(phe);
    phe_out = phe;
else
    phe_out = 0;
    phe_sign = 0;
end
% 模式控制
if cfg.dco_duty_calib_mode == 1
    phe_out = phe_sign;
end
% 延时控制
if cfg.dco_duty_calib_sel==1
    psel = sel_clk_fb_ff;
else
    psel = sel_clk_fb;
end
% 方向选择
if psel==0
    sel_out = (-1)*phe_out;
else
    sel_out = phe_out;
end
shift_out = cfg.dco_duty_calib_step*sel_out;
if rstn_calib==0
    integ = 0;
end
acc_out = integ + shift_out;
acc_out = round(acc_out*2^cfg.dco_calib_coef_frac_width)/2^cfg.dco_calib_coef_frac_width;
dco_calib_coef = integ;

% 输出补偿
if sel_clk_fb==0
    dco_dtc_comp = round(dco_calib_coef)*(-1);
else
    dco_dtc_comp = round(dco_calib_coef);
end

% reg update
integ = acc_out;
sel_clk_fb_ff = sel_clk_fb;