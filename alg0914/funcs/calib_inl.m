function [g2,acc_out] = calib_inl(rstn_calib,phe,eq,cfg)


persistent integ 
persistent inl_start_cnt 

if isempty(integ)
    integ = 0;
    inl_start_cnt = 0;
end

% 启动延时
if rstn_calib==1
    if inl_start_cnt>=floor(150e-6*cfg.fref)
        inl_start_en = 1;
    else
        inl_start_en = 0;
        inl_start_cnt = inl_start_cnt + 1;
    end
else
    inl_start_en = 0;
end

% 支持sing-lms
if cfg.kdtc_calib_mode==1
    phe = sign(phe);
end

if cfg.inl_calib_en==1 && inl_start_en==1
    phe_out = phe;
else
    phe_out = 0;
end

% corr
multi = phe_out*eq^2;
shift_out = multi*cfg.inl_calib_step;

if rstn_calib==1
    acc_out = integ + shift_out;
    acc_out = round(acc_out*2^cfg.kdtc_frac_width)/2^cfg.kdtc_frac_width;
else
    integ = 0;
    acc_out = integ + shift_out;
    acc_out = round(acc_out*2^cfg.kdtc_frac_width)/2^cfg.kdtc_frac_width;
end

g2 = integ;

% reg update
integ = acc_out;