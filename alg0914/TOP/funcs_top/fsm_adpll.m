function [state_next,ctl] = fsm_adpll(state,afc_finish,freq_lock,phase_lock,cfg)
% fsm_adpll — top FSM of rtl/adpll/adpll_fsm/adpll_fsm.v.
%   States: 0 IDLE, 1 AFC, 2 FLL, 3 PLL, 4 LOCK, 5 UNLOCK.
%   IDLE->AFC (unconditional), AFC->FLL (afc_finish), FLL->PLL (freq_lock),
%   PLL->LOCK (phase_lock), LOCK->UNLOCK (!phase_lock), UNLOCK->FLL.
%   Controls are combinational from the CURRENT state (registered state,
%   same-cycle flags), exactly like the RTL.  afc_finish is now the real
%   signal from afc_bisect (was tied 1 when AFC was skipped).
%
%   One documented deviation (cfg.fsm_lock_keep_fll, default 1):
%   adpll_fsm.v leaves rstn_fll=0 in ST_LOCK, which through the golden
%   funcs/fll.m clears freq_ctrl/freq_lock and collapses the loop.  The sim
%   keeps rstn_fll=1 with freq_lock_en=0 (FLL frozen, not reset) in LOCK.

ST_IDLE=0; ST_AFC=1; ST_FLL=2; ST_PLL=3; ST_LOCK=4; ST_UNLOCK=5;

switch state
    case ST_IDLE
        state_next = ST_AFC;
    case ST_AFC
        if afc_finish==1, state_next = ST_FLL; else, state_next = ST_AFC; end
    case ST_FLL
        if freq_lock==1, state_next = ST_PLL; else, state_next = ST_FLL; end
    case ST_PLL
        if phase_lock==1, state_next = ST_LOCK; else, state_next = ST_PLL; end
    case ST_LOCK
        if phase_lock==0, state_next = ST_UNLOCK; else, state_next = ST_LOCK; end
    case ST_UNLOCK
        state_next = ST_FLL;
    otherwise
        state_next = ST_IDLE;
end

% defaults: everything in reset, divider alive (mirrors RTL default arm)
ctl.rstn_mmd          = 1;
ctl.rstn_afc          = 0;
ctl.afc_calib_en      = 0;
ctl.lp_open           = 0;          % abank_code_cfg_mode (LPF open-loop cfg)
ctl.rstn_fll          = 0;
ctl.freq_lock_en      = 0;
ctl.rstn_dsm_fb       = 0;
ctl.rstn_lpf          = 0;
ctl.rstn_calib        = 0;
ctl.rstn_lock         = 0;
ctl.kdtc_calib_en     = 0;
ctl.ref_double_calib_en = 0;
ctl.dco_duty_calib_en = 0;

switch state
    case ST_AFC
        ctl.rstn_afc     = 1;        % per adpll_fsm.v ST_AFC arm
        ctl.afc_calib_en = 1;
        ctl.lp_open      = 1;        % Abank_code_cfg_mode=1 (Abank_code_cfg=256)
        ctl.rstn_mmd     = 1;
    case ST_FLL
        ctl.rstn_fll     = 1;
        ctl.freq_lock_en = 1;
        ctl.rstn_mmd     = 1;
    case ST_PLL
        ctl.rstn_fll     = 1;
        ctl.freq_lock_en = 0;
        ctl.rstn_mmd     = 1;
        ctl.rstn_dsm_fb  = 1;
        ctl.rstn_lpf     = 1;
        ctl.rstn_calib   = 1;
        ctl.rstn_lock    = 1;
        ctl.kdtc_calib_en     = 1;
        ctl.ref_double_calib_en = cfg.ref_double_en;   % only meaningful with doubling
        ctl.dco_duty_calib_en = 1;
    case ST_LOCK
        if isfield(cfg,'fsm_lock_keep_fll') && cfg.fsm_lock_keep_fll==1
            ctl.rstn_fll = 1;         % deviation: frozen, not reset (see header)
        end
        ctl.freq_lock_en = 0;
        ctl.rstn_mmd     = 1;
        ctl.rstn_dsm_fb  = 1;
        ctl.rstn_lpf     = 1;
        ctl.rstn_calib   = 1;
        ctl.rstn_lock    = 1;
        ctl.kdtc_calib_en     = 1;
        ctl.ref_double_calib_en = cfg.ref_double_en;
        ctl.dco_duty_calib_en = 1;
    case ST_UNLOCK
        ctl.rstn_mmd = 1;
    % IDLE: defaults only
end
end
