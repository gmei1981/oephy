Top-level ADPLL closed-loop simulation outputs (PHYSICAL three-bank DCO + full AFC)
Vector files are one integer per line per reference cycle (25 MHz), same conventions as RM/output.

DCO model (actual architecture, user-provided bank definitions):
  pbank 6b : 30 MHz band per code, 19.0 MHz spacing (cfg dco_pbank_step)
  abank 9b : 511 sub-steps over 30 MHz -> LSB 58.7084 kHz (cfg dco_abank_span)
  fbank 3b : lpf_frac -> SDM, 8 codes = 1 abank LSB
  f_dco = 7.6700 GHz + pbank*1.90476e+07 + ctrl*58708.414873 Hz
  loop retune: kp/ki scaled by fref/Ka (=426) vs the normalized model

Scaling of the dumped vectors (same conventions as RM/output):
  DBG/IND_phe_out, IND_phe : (s,18,16) LSBs, cycles = val/2^16
  DBG/IND_q_err            : (s,36,35) LSBs, DCO cycles = val/2^35
  DBG/IND_freq_ctrl        : (s,25,15) LSBs, now in abank-code units
  IND_lpf_frac, DBG_lpf_frac: (u,26,26) LSBs
  DBG_dco_freq_hz          : physical f_dco (Hz)
  DBG_kdtc                 : (s,34,24) LSBs
  DBG_pbank_code           : AFC-selected sub-band (6b)

FLL fb_cnt convention (pulse): IND_fb_cnt holds the fresh DCO/4 window
count only on the first cycle of each 512-cycle window and calc_cnt=10272
otherwise, which makes funcs/fll.m integrate once per window exactly like
rtl/adpll/fll/fll.v (ref_window_done_d).  Held or live counts diverge.

Modeling decisions (cfg-switchable):
 A. dsm_dco FREE-RUNS (adpll_fsm.v does not drive rstn_dsm_dco) at
    dsm_dco_oversample sub-steps per ref cycle; resetting it during FLL
    pins the fine bank -> 25 MHz-ish deadband, ref-rate dither breaks FLL.
 B. Fine bank: 8 codes = 1 abank LSB, DSM input mod(8f,1) + static floor(8f)
    (RM/dsm_dco_rm.m drives lpf_frac directly — placeholder, mean off by f/8).
 C. FLL first active call feeds fb_cnt=0 (fll.m latches calc_cnt_reg one
    call late; rtl/adpll/fll/fll.v initializes fb_count_delta for this).
 D. kdtc LMS at LAG 0 (cfg.kdtc_lms_delay): the RM fixed 2-sample delay
    anti-converges at frac=0.25 (period-4 sawtooth, half-period lag).
 E. lpf.m quantizes ki to the 2^-10 grid: ki < 2^-10 rounds to ZERO.
 F. FLL loop gain is Kvco-limited (Ka/(4*fref) per cycle): with the physical
    58.7 kHz abank LSB the count LSB (195 kHz @ 512-cycle DCO/4 window) is
    3.33x coarser than a code, so freq_ctrl walks at ~0.3 window-gain —
    freq_lock_thr=15 declares early and the PLL absorbs the remainder.
 G. TEMPORARY 1-bit fbank (dsm_dco_mode=0): single cell of 1 abank LSB on a
    1st-order SDM fed the full lpf_frac; quantization phase ripple is only
    Ka/(K*fref) ~ 3.7 fs at dsm_dco_oversample=20 (clk_dsm = fDCO/4 =
    FCW/4 sub-steps per ref cycle; 3-bit path kept, mode=2).
 H. DTC plant per spec table: per-code INL 2.0 LSB RMS (smooth random curve)
    + DNL 1.0 LSB RMS (non-accumulating cell mismatch, see dtc_inl_table)
    and PN floor -160 dBc/Hz @100 MHz = 159 fs RMS white edge jitter
    (dtc_pn_sigma); the synthetic quadratic dtc_inl2_a is now 0.

Known RM/RTL discrepancies found while building this sim (model wins here):
 1. fll.v expected_count = FCW_int*2^thr vs fll.m calc_cnt = FCW*2^thr/4 (=> fb clock is DCO/4)
 2. adpll_fsm.v ST_LOCK drives rstn_fll=0 (would clear freq_ctrl); sim keeps FLL frozen (fsm_lock_keep_fll=1)
 3. funcs/lpf.m kp/ki selection is inverted vs the spec table and lpf.v (kp1 = pre-lock there)
 4. RM cfg lock_cnt_thr=256 is an exponent (2^256, never locks); top cfg uses 8
 5. dco_duty_calibration_cfg.txt IND_sel_clk_fb path points at IND_dco_dtc_comp.txt
 6. pbank_afc.v expected_count = trial_code<<8 is an unfinished placeholder;
    the sim uses the spec semantics expected = FCW/afc_div*2^afc_ref_cnt_thr
