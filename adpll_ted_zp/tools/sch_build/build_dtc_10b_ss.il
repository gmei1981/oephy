cv = dbOpenCellViewByType("adpll_sch" "dtc_10b_ss" "schematic" "schematic" "a")

procedure(rsProp(inst prop val)
  if(dbFindProp(inst prop)
    dbReplaceProp(inst prop "string" val)
    dbCreateProp(inst prop "string" val)))

procedure(rsTermCtr(inst termName)
  let((term pin fig bb)
    term = car(setof(tt inst~>master~>terminals tt~>name == termName))
    pin = when(term car(term~>pins))
    fig = when(pin car(pin~>figs))
    bb = when(fig fig~>bBox)
    when(bb
      dbTransformPoint(
        list((xCoord(car(bb)) + xCoord(cadr(bb))) / 2.0
             (yCoord(car(bb)) + yCoord(cadr(bb))) / 2.0)
        inst~>transform))))

procedure(rsStub(inst termName netName dx dy)
  let((ctr end mid)
    ctr = rsTermCtr(inst termName)
    when(ctr
      end = list(xCoord(ctr) + dx yCoord(ctr) + dy)
      mid = list((xCoord(ctr) + xCoord(end)) / 2.0
                 (yCoord(ctr) + yCoord(end)) / 2.0)
      schCreateWire(cv "route" "full" list(ctr end) 0 0 0 nil nil)
      schCreateWireLabel(cv nil mid netName "centerCenter" "R0" "stick" 0.0625 nil))))

procedure(rsPinAt(pinName dir x y)
  let((master)
    master = dbOpenCellViewByType("basic"
      cond((dir == "input" "ipin") (dir == "output" "opin") (t "iopin"))
      "symbol")
    schCreatePin(cv master pinName dir nil x:y "R0")
    schCreateWire(cv "route" "full" list(x:y x+0.5:y) 0 0 0 nil nil)
    schCreateWireLabel(cv nil x+0.25:y pinName "centerCenter" "R0" "stick" 0.0625 nil)))
; ---- decoder VA inside DTC (10b passthrough) ----
; pll_dtc_code symbol is a ~310-wide horizontal bar (1033 pins, 0.3 pitch);
; keep its pin row clear of the grid top-row D stubs (y ends 26.44)
xdec = dbCreateInstByMasterName(cv "adpll_sch" "pll_dtc_code" "symbol" "Xdec" 4:32 "R0")
rsProp(xdec "vth" "0.5")

; ---- peripherals (identical to dtc_10b) ----
R0 = dbCreateInstByMasterName(cv "tsmcN12" "rhim" "symbol" "R0" 10:20 "R0")
rsProp(R0 "l" "2.3e-06")
rsProp(R0 "w" "2e-06")
MNI = dbCreateInstByMasterName(cv "tsmcN12" "nch_svt_mac" "symbol" "MNI" 14:20 "R0")
rsProp(MNI "fingers" "1") rsProp(MNI "nf" "1")
MPI = dbCreateInstByMasterName(cv "tsmcN12" "pch_svt_mac" "symbol" "MPI" 16:20 "R0")
rsProp(MPI "fingers" "1") rsProp(MPI "nf" "1")
MRST_D = dbCreateInstByMasterName(cv "tsmcN12" "nch_svt_mac" "symbol" "MRST_D" 18:20 "R0")
rsProp(MRST_D "fingers" "2") rsProp(MRST_D "nf" "2")
MN1 = dbCreateInstByMasterName(cv "tsmcN12" "nch_svt_mac" "symbol" "MN1" 22:20 "R0")
rsProp(MN1 "fingers" "8") rsProp(MN1 "nf" "8")
MP1 = dbCreateInstByMasterName(cv "tsmcN12" "pch_svt_mac" "symbol" "MP1" 24:20 "R0")
rsProp(MP1 "fingers" "8") rsProp(MP1 "nf" "8")

rsStub(R0 "PLUS" "CK_IN" -0.25 0)
rsStub(R0 "MINUS" "VDLY" 0.25 0)
rsStub(MNI "G" "CK_IN" -0.25 0) rsStub(MNI "D" "CKXB" 0 0.25)
rsStub(MNI "S" "VSS" 0 -0.25) rsStub(MNI "B" "VSS" 0.25 0)
rsStub(MPI "G" "CK_IN" -0.25 0) rsStub(MPI "D" "CKXB" 0 -0.25)
rsStub(MPI "S" "VDD" 0 0.25) rsStub(MPI "B" "VDD" 0.25 0)
rsStub(MRST_D "G" "CKXB" -0.25 0) rsStub(MRST_D "D" "VDLY" 0 0.25)
rsStub(MRST_D "S" "VSS" 0 -0.25) rsStub(MRST_D "B" "VSS" 0.25 0)
rsStub(MN1 "G" "VDLY" -0.25 0) rsStub(MN1 "D" "CK_OUT" 0 0.25)
rsStub(MN1 "S" "VSS" 0 -0.25) rsStub(MN1 "B" "VSS" 0.25 0)
rsStub(MP1 "G" "VDLY" -0.25 0) rsStub(MP1 "D" "CK_OUT" 0 -0.25)
rsStub(MP1 "S" "VDD" 0 0.25) rsStub(MP1 "B" "VDD" 0.25 0)

; ---- 33x31 grid: 1023 switch+cap pairs ----
for(row 0 32
  for(col 0 30
    let((i x y uname cname ui ci)
      i = row*31 + col
      x = 150.0 + col*2.5
      y = 26.0 - row*2.0
      uname = sprintf(nil "U%d" i)
      cname = sprintf(nil "C%d" i)
      ui = dbCreateInstByMasterName(cv "tsmcN12" "nch_svt_mac" "symbol" uname x:y "R0")
      rsProp(ui "fingers" "2") rsProp(ui "nf" "2")
      ci = dbCreateInstByMasterName(cv "analogLib" "cap" "symbol" cname x+1.2:y "R0")
      rsProp(ci "c" "5e-16")
      rsStub(ui "G" sprintf(nil "c%d" i) -0.25 0)
      rsStub(ui "D" "VDLY" 0 0.25)
      rsStub(ui "S" sprintf(nil "UCAP%d" i) 0 -0.25)
      rsStub(ui "B" "VSS" 0.25 0)
      rsStub(ci "PLUS" sprintf(nil "UCAP%d" i) 0 0.25)
      rsStub(ci "MINUS" "VSS" 0 -0.25))))

; ---- Xdec pin stubs: code<i> -> CODE<i>, c<i> stays ----
foreach(tname xdec~>master~>terminals~>name
  let((net)
    net = cond(
      (tname == "code0" "CODE0")
      (tname == "code1" "CODE1")
      (tname == "code2" "CODE2")
      (tname == "code3" "CODE3")
      (tname == "code4" "CODE4")
      (tname == "code5" "CODE5")
      (tname == "code6" "CODE6")
      (tname == "code7" "CODE7")
      (tname == "code8" "CODE8")
      (tname == "code9" "CODE9")
      (t tname))
    rsStub(xdec tname net 0 0.3)))

; ---- 14 pins in subckt header order ----
rsPinAt("CK_IN" "input" 1.0 18.0)
rsPinAt("CK_OUT" "output" 1.0 16.0)
rsPinAt("VDD" "inputOutput" 1.0 14.0)
rsPinAt("VSS" "inputOutput" 1.0 12.0)
rsPinAt("CODE0" "input" 1.0 10.0)
rsPinAt("CODE1" "input" 1.0 8.0)
rsPinAt("CODE2" "input" 1.0 6.0)
rsPinAt("CODE3" "input" 1.0 4.0)
rsPinAt("CODE4" "input" 1.0 2.0)
rsPinAt("CODE5" "input" 1.0 0.0)
rsPinAt("CODE6" "input" 1.0 -2.0)
rsPinAt("CODE7" "input" 1.0 -4.0)
rsPinAt("CODE8" "input" 1.0 -6.0)
rsPinAt("CODE9" "input" 1.0 -8.0)

printf("DTCSS_BUILD_DONE instances=%d\n" length(cv~>instances))
