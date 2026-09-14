function [pbank_code,afc_finish,A] = afc_bisect(A,afc_fresh,afc_delta,expected,afc_en)
% afc_bisect — pbank binary-search AFC, faithful to rtl/adpll/pbank_afc.v
%   and the spec (ADPLL算法方案设计报告 §3).
%
%   Trial code starts at 32 (mid of 0..63); step halves 32->16->...->1.
%   Every completed measurement window arrives as a one-cycle afc_fresh
%   pulse carrying afc_delta (the DCO/afc_div edge count over the window).
%   On each pulse:
%     err = afc_delta - expected          (expected = FCW/afc_div*2^afc_thr,
%                                          the spec's theoretical count; the
%                                          RTL's expected_count is an
%                                          unfinished placeholder trial<<8)
%     keep the min-|err| code             (spec: 记录偏差最小的控制位)
%     step: err < 0 (freq low) -> trial += step; else trial -= step
%     step == 0 -> pbank_code = best, afc_finish = 1
%   The trial only changes right after a pulse, so each window measures a
%   settled pbank (same boundary trick as the FLL pulse convention).
%   Direction convention: higher pbank = higher frequency (RTL FSM_NEXT).

if isempty(A)
    A = struct('state',0,'step',32,'trial',32,'best_code',32, ...
               'best_err',inf,'pbank_code',32,'finish',0);
end

if afc_en==0
    % search state resets, but the CALIBRATED pbank_code output is HELD:
    % rtl/adpll/pbank_afc.v clears pbank_code to 0 in its !afc_calib_en
    % branch, which would lose the result the moment the FSM leaves ST_AFC
    % (recorded in the discrepancy list).
    A.state = 0; A.step = 32; A.trial = 32; A.best_code = 32;
    A.best_err = inf; A.finish = 0;
    pbank_code = A.pbank_code;
    afc_finish = 0;
    return;
end

if A.state==0
    % IDLE: apply the first trial, wait for its window
    A.state = 1;
    A.pbank_code = A.trial;
elseif A.state==1
    A.pbank_code = A.trial;   % output follows the trial (RTL WAIT_WIN)
    if afc_fresh==1
        err = afc_delta - expected;
        if abs(err) < A.best_err
            A.best_err = abs(err);
            A.best_code = A.trial;
        end
        if A.step==0
            A.pbank_code = A.best_code;
            A.finish = 1;
            A.state = 2;
        else
            if err < 0
                A.trial = A.trial + A.step;   % count low = freq low -> up
            else
                A.trial = A.trial - A.step;   % freq high -> down
            end
            A.trial = min(max(A.trial,0),63);
            A.step = floor(A.step/2);
            A.pbank_code = A.trial;
        end
    end
end

pbank_code = A.pbank_code;
afc_finish = A.finish;
end
