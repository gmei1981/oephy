; ref3_va.il — build VA module cells (symbol + CDF) for ref3 digital blocks.
; Driven by tools/build_va_ref3.py via `vlink evalstring`.
; Conventions follow the proven dtc_10b manual symbol API (IC618-safe):
;   pin = net + terminal + pin/drawing rect + pin-name label.
; Labels use core dbCreateLabel (+labelType attr for NLP) because
; schCreateSymbolLabel is unavailable in this session's editor env.

procedure( ref3VaLbl(cv lpp x y text just ltype)
  let((lb)
    lb = dbCreateLabel(cv lpp list(x y) text just "R0" "stick" 0.0625)
    when(ltype && lb lb~>labelType = ltype)
    unless(lb error(strcat("label not created: " text)))
    lb
  )
)

procedure( ref3VaWipe(lib cell view)
  ; in-place purge (dbDeleteCellView unavailable in this session's env)
  let((cv)
    cv = dbOpenCellViewByType(lib cell view "" "a")
    when(cv
      foreach(x copy(cv~>pins) dbDeleteObject(x))
      foreach(x copy(cv~>figures) dbDeleteObject(x))
      foreach(x copy(cv~>terminals) dbDeleteObject(x))
      foreach(x copy(cv~>nets) dbDeleteObject(x))
      dbSave(cv)
    )
    t
  )
)

; ---- symbol builder ----------------------------------------------------
; ports: list of lists (name direction x y labelJustification labelX labelY)
; body:  list(x0 y0 x1 y1);  selBox: list(x0 y0 x1 y1)
; instLabel/logical: list(x y)
procedure( ref3VaSym(lib cell ports body selBox instLblPos logLblPos)
  let((cv pin)
    ref3VaWipe(lib cell "symbol")
    cv = dbOpenCellViewByType(lib cell "symbol" "schematicSymbol" "a")
    unless(cv error("cannot open symbol cellview"))
    dbCreateRect(cv list("device" "drawing")
                 list(list(nth(0 body) nth(1 body)) list(nth(2 body) nth(3 body))))
    foreach(p ports
      ; p = (name direction x y just lx ly)
      let((net term fig)
        net = dbCreateNet(cv nth(0 p))
        term = dbCreateTerm(net nth(0 p) nth(1 p))
        fig = dbCreateRect(cv list("pin" "drawing")
                 list(list(nth(2 p)-0.0625 nth(3 p)-0.0625)
                      list(nth(2 p)+0.0625 nth(3 p)+0.0625)))
        pin = dbCreatePin(net fig nth(0 p) term)
        unless(pin error(strcat("pin not created: " nth(0 p))))
      )
    )
    ; pin-name labels on pin/label (cosmetic; netlisting uses terminals)
    foreach(p ports
      ref3VaLbl(cv list("pin" "label") nth(5 p) nth(6 p) nth(0 p)
                nth(4 p) nil)
    )
    ref3VaLbl(cv list("instance" "label")
              nth(0 instLblPos) nth(1 instLblPos) "[@instanceName]"
              "centerCenter" "NLPLabel")
    ref3VaLbl(cv list("instance" "label")
              nth(0 logLblPos) nth(1 logLblPos) "[@partName]"
              "centerCenter" "NLPLabel")
    dbCreateRect(cv list("instance" "drawing")
                 list(list(nth(0 selBox) nth(1 selBox))
                      list(nth(2 selBox) nth(3 selBox))))
    ; termOrder informational (si uses CDF order for symbol-only cells)
    cv~>termOrder = mapcar(lambda((p) nth(0 p)) ports)
    dbSave(cv)
    dbClose(cv)
    t
  )
)

; ---- CDF builder -------------------------------------------------------
; portNames/portDirs: parallel lists in module declaration order.
; params: list of (name type def) with type "float"/"int"/"string".
procedure( ref3VaCdf(lib cell portNames portDirs params)
  let((cdfId obj)
    obj = ddGetObj(lib cell)
    when(obj && cdfGetBaseCellCDF(obj)
      ; idempotent: clear all params over a copy, keep the CDF object
      cdfId = cdfGetBaseCellCDF(obj)
      foreach(pp copy(cdfId~>parameters) cdfDeleteParam(pp))
    )
    unless(cdfId
      cdfId = cdfCreateBaseCellCDF(ddGetObj(lib cell))
      unless(cdfId error("cdf create failed"))
    )
    ; module parameters (instance override-able); all declared "string"
    ; (the pattern the existing VA cells use — values emit verbatim).
    ; Pin connectivity/order comes from the symbol view terminals.
    foreach(p params
      cdfCreateParam(cdfId
        ?name nth(0 p) ?type "string"
        ?defValue nth(2 p) ?prompt nth(0 p))
    )
    cdfId~>cellClass = "module"
    cdfId~>simInfo = list(nil
      list("spectre"
        list("netlistTypeName" "subcircuit"
             "instNamePrefix" "X"
             "termOrder" portNames)))
    cdfSaveCDF(cdfId)
    t
  )
)

; ---- readback ----------------------------------------------------------
procedure( ref3VaRead(lib cell)
  let((cv terms pins params)
    cv = dbOpenCellViewByType(lib cell "symbol" "schematicSymbol" "r")
    unless(cv error("no symbol view"))
    terms = cv~>termOrder
    dbClose(cv)
    pins = terms   ; termOrder == creation order here
    sprintf(nil "TERMS %L" terms)
  )
)

procedure( ref3VaCdfRead(lib cell)
  let((cdfId)
    cdfId = cdfGetBaseCellCDF(ddGetObj(lib cell))
    unless(cdfId error("no cdf"))
    sprintf(nil "CDFPINS %L PARAMS %L SIMINFO %L"
      cdfId~>pinOrder
      mapcar(lambda((pp) list(pp~>name pp~>paramType pp~>defValue))
             setof(pp cdfId~>parameters !member(pp~>paramType '("pin"))))
      cdfId~>simInfo)
  )
)
