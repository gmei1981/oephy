function [freq_ctrl,freq_lock,calc_cnt,fll_freq_err,freq_shift] = fll(rstn_fll,fb_cnt,cfg)

persistent freq_ref_cnt
persistent calc_cnt_reg
persistent freq_ctrl_reg
persistent freq_lock_reg
persistent freq_lock_cnt



if isempty(freq_ref_cnt)
    freq_ref_cnt = 0;
    calc_cnt_reg = 0;
    freq_ctrl_reg = 0;
    freq_lock_reg = 0;
    freq_lock_cnt = 0;
end

% output
freq_ctrl = freq_ctrl_reg;
freq_lock = freq_lock_reg;


% ref_calc
shift_right = floor(2^cfg.fcw_frac_width*cfg.adpll_fcw/2^2)/2^cfg.fcw_frac_width;
calc_cnt = floor(shift_right*2^cfg.freq_ref_cnt_thr);

% freq_fref_cnt
freq_ref_cnt_acc = freq_ref_cnt + cfg.freq_lock_en;
if freq_ref_cnt>=2^cfg.freq_ref_cnt_thr
    ref_update = 0;
else
    ref_update = 1;
end
% sample
if ref_update==1
    calc_cnt_sel_out = calc_cnt; 
else
    calc_cnt_sel_out = calc_cnt_reg;
end
fll_freq_err = calc_cnt_reg - fb_cnt;

% 误差处理
if freq_lock_reg==1
    fll_freq_err_sel = 0;
else
    fll_freq_err_sel = fll_freq_err;
end
freq_shift = fll_freq_err_sel/2^cfg.freq_lock_step;

freq_integ_acc = freq_shift + freq_ctrl_reg;

% lock
abs_out = abs(fll_freq_err_sel);
if abs_out<=cfg.freq_lock_thr
    if freq_lock_reg==0
        lock_en = cfg.freq_lock_en;
    else
        lock_en = 0;
    end
    freq_lock_cnt_acc = freq_lock_cnt + lock_en;
else
    freq_lock_cnt_acc = 0;
end
if freq_lock_cnt>=2^cfg.freq_ref_cnt_thr+10
    freq_lock_sel_out = 1;
else
    freq_lock_sel_out = freq_lock_reg;
end

% reg update
if rstn_fll==0
    freq_ref_cnt = 0;
    freq_lock_cnt = 0;
    freq_ctrl_reg = 0;
    freq_lock_reg = 0;
    calc_cnt_reg = 0;
else
    freq_ref_cnt = freq_ref_cnt_acc;
    freq_lock_cnt = freq_lock_cnt_acc;
    freq_ctrl_reg = freq_integ_acc;
    freq_lock_reg = freq_lock_sel_out;
    calc_cnt_reg = calc_cnt_sel_out;
end


end

