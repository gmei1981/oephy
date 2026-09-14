function [phase_lock,dbg] = lock_detect(rstn_lock,phe,cfg)

persistent time
persistent lock_cnt
persistent unlock_cnt
persistent lock_reg

if isempty(time)
    time = 0;
    lock_cnt = 0;
    unlock_cnt = 0;
    lock_reg = 0;
end

phe_abs = abs(phe);
phase_lock = lock_reg;
if lock_reg==1
    % 锁定情况喜下判定失锁
    if phe_abs>=cfg.unlock_phe_thr
        unlock_cnt = unlock_cnt + 1;
        if unlock_cnt>=2^cfg.unlock_cnt_thr
            lock_reg = 0;
            unlock_cnt = 0;
        end
    else
        unlock_cnt = 0;
    end
else
    % 失锁情况下判断锁定
    if phe_abs<=cfg.lock_phe_thr
        lock_cnt = lock_cnt + 1;
        if lock_cnt>=2^cfg.lock_cnt_thr
            lock_reg = 1;
            lock_cnt = 0;
        end
    else
        lock_cnt = 0;
    end

end

if rstn_lock==0
    lock_cnt = 0;
    unlock_cnt = 0;
    lock_reg = 0;
end

dbg.phe_abs = phe_abs;
dbg.phase_lock = phase_lock;

