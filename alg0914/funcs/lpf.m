function lpf_out = lpf(rstn_lpf,phase_lock,afc_finish,freq_lock,phe,freq_ctrl,cfg)

persistent integ

if isempty(integ)
    integ = 0;
end

% 带宽选择
if phase_lock==1
    kp = round(cfg.kp1*2^cfg.kp_frac_width)/2^cfg.kp_frac_width;
    ki = round(cfg.ki1*2^cfg.ki_frac_width)/2^cfg.ki_frac_width;
else
    kp = round(cfg.kp2*2^cfg.kp_frac_width)/2^cfg.kp_frac_width;
    ki = round(cfg.ki2*2^cfg.ki_frac_width)/2^cfg.ki_frac_width;
end
% phe选择
if freq_lock==1
    phe_out = phe;
else
    phe_out = 0;
end
acc_out = integ + ki*phe_out;
lpf_out = kp*phe_out + integ + freq_ctrl;
% AFC时Abank码值和Fbank码值设置为0
if afc_finish==0
    lpf_out = 0;
end
% 开环软件配置Abank码值
if cfg.open_loop_en==1
    lpf_out = cfg.Abank_code_sw;
end

% reg update
if rstn_lpf==1
    integ = acc_out;
else
    integ = 0;
end



