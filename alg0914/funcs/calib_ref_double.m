function [even_cycle,ref_calib_coef,ref_calib_comp]  = calib_ref_double(phe,rstn_calib,cfg)

persistent cycle_cnt
persistent integ
persistent phe_ff
persistent even_cycle_ff


if isempty(cycle_cnt)
    cycle_cnt = 0;
    integ = 0;
    phe_ff = 0;
    even_cycle_ff = 0;
end

% 参考倍频校准使能
if cfg.ref_double_en==1
    % 区分奇数和偶数
    cycle_cnt_acc = cycle_cnt + 1;
    if mod(cycle_cnt,2)==0
        even_cycle = 0;
    else
        even_cycle = 1;
    end
    % reg update
    cycle_cnt = cycle_cnt_acc;
else
    even_cycle = 0;
end
% 方向选择
if cfg.ref_double_calib_sel==1
    ref_sel = even_cycle_ff;
else
    ref_sel = even_cycle;
end
% 参考倍频校准使能
if cfg.ref_double_calib_en==1
    phe_out = phe;
else
    phe_out = 0;
end
if cfg.ref_double_calib_mode==1
    phe_out = sign(phe_out);
end
% 偏差信息
freq_err = phe_out - phe_ff;
if ref_sel==1
    sel_out = freq_err*(-1);
else
    sel_out = freq_err;
end
shift_out = cfg.ref_double_calib_step*sel_out;
if rstn_calib==0
    integ = 0;
end
acc_out = integ + shift_out;
acc_out = round(acc_out*2^cfg.ref_calib_coef_frac_width)/2^cfg.ref_calib_coef_frac_width;
ref_calib_coef = integ;

% comp
if ref_sel==0
    ref_calib_comp = ref_calib_coef*(-1);
else
    ref_calib_comp = ref_calib_coef;
end


% reg update
phe_ff = phe_out;
integ = acc_out;
even_cycle_ff = even_cycle;


