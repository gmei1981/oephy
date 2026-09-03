;; auto-generated schematic drawing script for cmp_x
;
(let ((cv nil) (inst nil) (ip nil) (trm nil) (a1 nil) (a2 nil) (anch nil) (xm 0.0))
  (unless (ddGetObj "adpll_sch") (dbCreateLib "adpll_sch"))
  (setq cv (dbOpenCellViewByType "adpll_sch" "cmp_x" "schematic" "schematic" "a"))
  ;; ---- instances ----
  (setq ih (makeTable 'ih nil))
  (setq inst (dbCreateInstByMasterName cv "tsmcN12" "pch_svt_mac" "symbol" "MP2" 0:0 "R0"))
  (setarray ih "MP2" inst)
  inst~>l = 1.6e-08
  inst~>nfin = 2
  inst~>w = 5.8e-08
  inst~>multi = 1
  inst~>nf = 2
  inst~>sd = 7.4e-08
  inst~>sa = 9e-08
  inst~>sb = 9e-08
  inst~>ploda1 = 1.6e-08
  inst~>ploda2 = 0
  inst~>ploda3 = 0
  inst~>plodb1 = 1.6e-08
  inst~>plodb2 = 0
  inst~>plodb3 = 0
  inst~>nf_flag = 1
  inst~>smbt = 1000000
  inst~>smbb = 1000000
  inst~>dinsaflag = 0
  inst~>ppitch = 0
  inst~>spot = 1.03e-07
  inst~>spob = 1.03e-07
  inst~>spotl1 = 1.03e-07
  inst~>spobl1 = 1.03e-07
  inst~>spotl2 = 1.03e-07
  inst~>spobl2 = 1.03e-07
  inst~>spotr1 = 1.03e-07
  inst~>spobr1 = 1.03e-07
  inst~>spotr2 = 1.03e-07
  inst~>spobr2 = 1.03e-07
  (setq inst (dbCreateInstByMasterName cv "tsmcN12" "nch_svt_mac" "symbol" "MN2" 0:-4 "R0"))
  (setarray ih "MN2" inst)
  inst~>l = 1.6e-08
  inst~>nfin = 2
  inst~>w = 5.8e-08
  inst~>multi = 1
  inst~>nf = 2
  inst~>sd = 7.4e-08
  inst~>sa = 9e-08
  inst~>sb = 9e-08
  inst~>ploda1 = 1.6e-08
  inst~>ploda2 = 0
  inst~>ploda3 = 0
  inst~>plodb1 = 1.6e-08
  inst~>plodb2 = 0
  inst~>plodb3 = 0
  inst~>nf_flag = 1
  inst~>smbt = 1000000
  inst~>smbb = 1000000
  inst~>dinsaflag = 0
  inst~>ppitch = 0
  inst~>spot = 1.03e-07
  inst~>spob = 1.03e-07
  inst~>spotl1 = 1.03e-07
  inst~>spobl1 = 1.03e-07
  inst~>spotl2 = 1.03e-07
  inst~>spobl2 = 1.03e-07
  inst~>spotr1 = 1.03e-07
  inst~>spobr1 = 1.03e-07
  inst~>spotr2 = 1.03e-07
  inst~>spobr2 = 1.03e-07
  (setq inst (dbCreateInstByMasterName cv "tsmcN12" "pch_svt_mac" "symbol" "MP1" 4:0 "R0"))
  (setarray ih "MP1" inst)
  inst~>l = 1.6e-08
  inst~>nfin = 2
  inst~>w = 5.8e-08
  inst~>multi = 1
  inst~>nf = 2
  inst~>sd = 7.4e-08
  inst~>sa = 9e-08
  inst~>sb = 9e-08
  inst~>ploda1 = 1.6e-08
  inst~>ploda2 = 0
  inst~>ploda3 = 0
  inst~>plodb1 = 1.6e-08
  inst~>plodb2 = 0
  inst~>plodb3 = 0
  inst~>nf_flag = 1
  inst~>smbt = 1000000
  inst~>smbb = 1000000
  inst~>dinsaflag = 0
  inst~>ppitch = 0
  inst~>spot = 1.03e-07
  inst~>spob = 1.03e-07
  inst~>spotl1 = 1.03e-07
  inst~>spobl1 = 1.03e-07
  inst~>spotl2 = 1.03e-07
  inst~>spobl2 = 1.03e-07
  inst~>spotr1 = 1.03e-07
  inst~>spobr1 = 1.03e-07
  inst~>spotr2 = 1.03e-07
  inst~>spobr2 = 1.03e-07
  (setq inst (dbCreateInstByMasterName cv "tsmcN12" "nch_svt_mac" "symbol" "MN1" 4:-4 "R0"))
  (setarray ih "MN1" inst)
  inst~>l = 1.6e-08
  inst~>nfin = 2
  inst~>w = 5.8e-08
  inst~>multi = 1
  inst~>nf = 2
  inst~>sd = 7.4e-08
  inst~>sa = 9e-08
  inst~>sb = 9e-08
  inst~>ploda1 = 1.6e-08
  inst~>ploda2 = 0
  inst~>ploda3 = 0
  inst~>plodb1 = 1.6e-08
  inst~>plodb2 = 0
  inst~>plodb3 = 0
  inst~>nf_flag = 1
  inst~>smbt = 1000000
  inst~>smbb = 1000000
  inst~>dinsaflag = 0
  inst~>ppitch = 0
  inst~>spot = 1.03e-07
  inst~>spob = 1.03e-07
  inst~>spotl1 = 1.03e-07
  inst~>spobl1 = 1.03e-07
  inst~>spotl2 = 1.03e-07
  inst~>spobl2 = 1.03e-07
  inst~>spotr1 = 1.03e-07
  inst~>spobr1 = 1.03e-07
  inst~>spotr2 = 1.03e-07
  inst~>spobr2 = 1.03e-07
  (setq inst (dbCreateInstByMasterName cv "tsmcN12" "nch_svt_mac" "symbol" "MTAIL" 8:-4 "R0"))
  (setarray ih "MTAIL" inst)
  inst~>l = 1.6e-08
  inst~>nfin = 2
  inst~>w = 5.8e-08
  inst~>multi = 1
  inst~>nf = 2
  inst~>sd = 7.4e-08
  inst~>sa = 9e-08
  inst~>sb = 9e-08
  inst~>ploda1 = 1.6e-08
  inst~>ploda2 = 0
  inst~>ploda3 = 0
  inst~>plodb1 = 1.6e-08
  inst~>plodb2 = 0
  inst~>plodb3 = 0
  inst~>nf_flag = 1
  inst~>smbt = 1000000
  inst~>smbb = 1000000
  inst~>dinsaflag = 0
  inst~>ppitch = 0
  inst~>spot = 1.03e-07
  inst~>spob = 1.03e-07
  inst~>spotl1 = 1.03e-07
  inst~>spobl1 = 1.03e-07
  inst~>spotl2 = 1.03e-07
  inst~>spobl2 = 1.03e-07
  inst~>spotr1 = 1.03e-07
  inst~>spobr1 = 1.03e-07
  inst~>spotr2 = 1.03e-07
  inst~>spobr2 = 1.03e-07
  (setq inst (dbCreateInstByMasterName cv "tsmcN12" "pch_svt_mac" "symbol" "MP3" 12:0 "R0"))
  (setarray ih "MP3" inst)
  inst~>l = 1.6e-08
  inst~>nfin = 2
  inst~>w = 5.8e-08
  inst~>multi = 1
  inst~>nf = 2
  inst~>sd = 7.4e-08
  inst~>sa = 9e-08
  inst~>sb = 9e-08
  inst~>ploda1 = 1.6e-08
  inst~>ploda2 = 0
  inst~>ploda3 = 0
  inst~>plodb1 = 1.6e-08
  inst~>plodb2 = 0
  inst~>plodb3 = 0
  inst~>nf_flag = 1
  inst~>smbt = 1000000
  inst~>smbb = 1000000
  inst~>dinsaflag = 0
  inst~>ppitch = 0
  inst~>spot = 1.03e-07
  inst~>spob = 1.03e-07
  inst~>spotl1 = 1.03e-07
  inst~>spobl1 = 1.03e-07
  inst~>spotl2 = 1.03e-07
  inst~>spobl2 = 1.03e-07
  inst~>spotr1 = 1.03e-07
  inst~>spobr1 = 1.03e-07
  inst~>spotr2 = 1.03e-07
  inst~>spobr2 = 1.03e-07
  (setq inst (dbCreateInstByMasterName cv "tsmcN12" "nch_svt_mac" "symbol" "MN3" 12:-4 "R0"))
  (setarray ih "MN3" inst)
  inst~>l = 1.6e-08
  inst~>nfin = 2
  inst~>w = 5.8e-08
  inst~>multi = 1
  inst~>nf = 2
  inst~>sd = 7.4e-08
  inst~>sa = 9e-08
  inst~>sb = 9e-08
  inst~>ploda1 = 1.6e-08
  inst~>ploda2 = 0
  inst~>ploda3 = 0
  inst~>plodb1 = 1.6e-08
  inst~>plodb2 = 0
  inst~>plodb3 = 0
  inst~>nf_flag = 1
  inst~>smbt = 1000000
  inst~>smbb = 1000000
  inst~>dinsaflag = 0
  inst~>ppitch = 0
  inst~>spot = 1.03e-07
  inst~>spob = 1.03e-07
  inst~>spotl1 = 1.03e-07
  inst~>spobl1 = 1.03e-07
  inst~>spotl2 = 1.03e-07
  inst~>spobl2 = 1.03e-07
  inst~>spotr1 = 1.03e-07
  inst~>spobr1 = 1.03e-07
  inst~>spotr2 = 1.03e-07
  inst~>spobr2 = 1.03e-07
  ;; (instances only: wiring/pins deferred to GUI or follow-up round)
  (dbSave cv)
  (geOpen ?lib "adpll_sch" ?cell "cmp_x" ?view "schematic" ?mode "r")
  (errset (hiExportImage (hiGetCurrentWindow) "/home/mei/adpll_sch_ws/cmp_x.png"))
  (sleep 3600)
  )
