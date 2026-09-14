function [kdtc,acc_out] = calib_kdtc(kdtc_start,rstn_calib,phe,eq,cfg)


persistent integ 
persistent kdtc_start_cnt 

if isempty(integ)
    integ = cfg.kdtc_initial;
    kdtc_start_cnt = 0;
end

% 启动延时
if rstn_calib==1
    if kdtc_start==1
        kdtc_start_en = 1;
    else
        kdtc_start_en = 0;
    end
else
    kdtc_start_en = 0;
end

% 支持sing-lms
if cfg.kdtc_calib_mode==1
    phe = sign(phe);
end

if cfg.kdtc_calib_en==1 && kdtc_start_en==1
    phe_out = phe;
else
    phe_out = 0;
end

% corr
multi = phe_out*eq;
shift_out = multi*cfg.kdtc_calib_step;

if rstn_calib==1
    acc_out = integ + shift_out;
    acc_out = round(acc_out*2^cfg.kdtc_frac_width)/2^cfg.kdtc_frac_width;
else
    integ = cfg.kdtc_initial;
    acc_out = integ + shift_out;
    acc_out = round(acc_out*2^cfg.kdtc_frac_width)/2^cfg.kdtc_frac_width;
end

kdtc = integ;

% reg update
integ = acc_out;