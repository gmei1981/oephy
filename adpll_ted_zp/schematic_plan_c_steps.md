# 原理图 Plan C 改造详细步骤（2026-09-02）

目标：把 scs 模块（`netlist/inc/vco_c.scs`、`netlist/inc/ldo_05.scs`、`sim/pll_step2_main_c.scs`）
落成原理图。参考网表逐行对照，验证工具 `tools/compare_semantic.py`（按端子名语义比对）+ 300ns 冒烟。

**总顺序**：① vco_x_c（内核）→ ② vco_dual_8g_c（双核）→ ③ ldo_05（新画）→ ④ adpll_top（改造）
→ ⑤ tb_adpll_top（加源）→ ⑥ 验证闭环。

**分工约定**：VAR 组 204 实例由桥批量放置（tools/build_vco_c.py，标签命名法零手绘，同 dtc_10b）；
删改/连线/Pins 由用户在 GUI 操作；我负责桥脚本 + si 导出 + 语义比对 + 冒烟。

---

## 1. vco_x_c（从 vco_x_8g 复制改造）

### 1.1 复制与 GUI 清理

```bash
cd virtuoso_ws/adpll_sch && cp -r vco_x_8g vco_x_c
```
（master.tag 只记 oa 文件名、cell 名=目录名，直接拷安全——0901 已验证）

在 Virtuoso 打开 vco_x_c/schematic，做 5 件事：

1. **删 CV0/CV1**（两个 wr=538n nfin=12 大 moscap，被 VAR 组取代）
2. **MN0/MN1 换模型**：Q → Model name `nch_svt_mac` → `nch_ulvt_mac`（svt 在 0.5V 下起不了振）
3. **MN0/MN1 源极改接 TAIL**：断开源极→VSS 的线，源极打标签 `TAIL`
4. **加 Ls**：analogLib `ind`（l=2n, r=1）TAIL ↔ VSS；**加 Cbyp**：`cap` c=10p，VDD ↔ VSS
5. **CF0-11 参数**：12 个 cfmom `nr` 192 → **188**（标定值回写）

### 1.2 VAR 组桥批量放置（我执行 build_vco_c.py）

放置 204 实例（每单元 3 器件 × 68 单元），实例名/参数与 `netlist/inc/vco_c.scs` 逐字一致：

| 组 | EN pin | 单元数/侧 | moscap nfin | 实例名 |
|---|---|---|---|---|
| VAR_I bit0 | ENI0 | 1 | 2 | VI00p/VI00n |
| VAR_I bit1 | ENI1 | 1 | 2 | VI10p/VI10n |
| VAR_I bit2 | ENI2 | 1 | 4 | VI20p/VI20n |
| VAR_P bit0-4 | ENP0-4 | 1/2/4/8/16 | 1 | VP00p…VP415p / VP00n…VP415n |

每单元结构（p 侧示例，n 侧镜像到 OUTN）：
```
VI00p_mv   moscap_rf  G=OUTP   B=VI00p_cb  gnode=VI00p_cb   wr=538n nfin=2 lr=200n gr=2 br=2
VI00p_sw   pch_svt    D=VI00p_cb  G=ENI0  S=VCTRL_I  B=VDD   nf=2 l=16n
VI00p_rb   rhim       VI00p_cb ↔ VDD   r=1M
```
（标签命名法：sw 源极打 `VCTRL_I`、栅极打 `ENI0`；rb 两端 `VI00p_cb`/`VDD`——
net 按标签名自动合并，零手绘连线）

### 1.3 GUI 少量收尾

- 确认 VAR 单元 cb 标签网与 sw/mv 合并正确（X Check 后无 floating：cb 网两实例、VCTRL_I/ENIx 总线全通）

### 1.4 Pins（14 个，按参考头顺序创建）

**先删旧 VCTRL pin**，然后严格按此顺序 P 建 pin（si 导出子电路头 = pin 创建序）：

```
VDD(inputOutput)  VSS(inputOutput)  VCTRL_P(input)  VCTRL_I(input)
OUTP(output)  OUTN(output)
ENI0 ENI1 ENI2 ENP0 ENP1 ENP2 ENP3 ENP4 (全 input)
```

接线：VDD/VSS/OUTP/OUTN 沿用原 pin；VCTRL_P/VCTRL_I 打到对应总线；EN* 打到对应总线。
**Symbol 同步**：Create Cellview From Cellview 重建 symbol（方向与 schematic 一致，
否则 schCheck 报 Terminal direction mismatch——vco_dual_8g 教训）。

### 1.5 验证

1. schCheck (0 0)
2. si 导出 vco_x_c → 与 `netlist/inc/vco_c.scs` 语义比对（端子名级）
3. 冒烟（闭环 60ns）确认 0.5V 核起振 f≈8.0G

---

## 2. vco_dual_8g_c（从 vco_dual_8g 复制改造）

1. `cp -r vco_dual_8g vco_dual_8g_c`
2. **Xa/Xb master 换 vco_x_c**：Q → Cell name `vco_x_8g` → `vco_x_c`；
   新增口接线：`VCTRL_P`/`VCTRL_I` 总线（两核共用同一控制线，论文同款）；
   `ENI0-2/ENP0-4` 总线
3. **MPWRB 源极**：VDD → **VDDC**（0.5V 轨上切核 B 供电）
4. **Pins（16 个，参考头顺序）**：加 `VDDC(inputOutput)`；加 8 个 EN 透传 pin；
   VCTRL 旧 pin 换成 VCTRL_P/VCTRL_I 两个。顺序：
   ```
   VDD VDDC VSS VCTRL_P VCTRL_I OUTP OUTN EN2 ENI0 ENI1 ENI2 ENP0 ENP1 ENP2 ENP3 ENP4
   ```
5. Symbol 重建（16 口）；schCheck + si 导出 + 语义比对 vco_c.scs 的 vco_dual_8g_c 段

---

## 3. ldo_05（新画，8 器件 + 6 pin）

全部器件（照 `netlist/inc/ldo_05.scs`）：

| 实例 | 器件/模型 | 参数 | 接线（D G S B） |
|---|---|---|---|
| MN1 | nch_**ulvt**_mac | nf=4 l=16n | VDN VOUT TAIL VSS |
| MN2 | nch_**ulvt**_mac | nf=4 l=16n | VDP VBG TAIL VSS |
| MTAIL | nch_**ulvt**_mac | nf=1 l=16n | TAIL VBL VSS VSS |
| MP1 | pch_svt_mac | nf=2 l=16n | VDN VDN VDD VDD |
| MP2 | pch_svt_mac | nf=2 l=16n | VDP VDN VDD VDD |
| MPASS | pch_svt_mac | **nf=256** l=16n | VOUT VGATE VIN VIN |
| RLPF | rhim | r=20k | VDP ↔ VGATE |
| CLPF | cap | c=8p | VGATE ↔ VSS |
| COUT | cap | c=20p | VOUT ↔ VSS |

**极性注意（坑已踩）**：VOUT 必须接 MN1（镜像侧/非反相）；VBG 接 MN2。
反了会正反馈锁死。输入对/尾管必须 ulvt（svt 在 0.5V 共模下打不开）。

Pins 6 个（参考头顺序）：`VDD VIN VBG VBL VOUT VSS`（VDD/VSS inputOutput，余 input/输出 VOUT=output）。

---

## 4. adpll_top 改造（删 4 加 3 换 1）

### 4.1 删除（VCTRL 合成链）
- 删实例：**Rf, Cf, Ep, Esum**（4 个）+ 网标签 VN1/VHF 清干净（GUI 清理会顺手删标签的坑！）

### 4.2 新控制接线
- **Xgm 不动**（IOUT=VI 原样）
- **VI → Xvco.VCTRL_I**：直连（同网名）
- **VHOLD → Ebufp → Xvco.VCTRL_P**：放 analogLib vcvs `Ebufp` gain=1
  （IN+=VHOLD, IN-=gnd!, OUT+=VCTRL_P, OUT-=gnd!）——理想缓冲 v1 占位

### 4.3 换 Xvco master 并接 16 口
- Xvco：Q → Cell `vco_dual_8g` → `vco_dual_8g_c`
- 接线：VDD→VDD、VDDC→**Xldo.VOUT**（内部网 VDDC，不引 pin）、VSS→VSS、
  VCTRL_P→Ebufp 输出、VCTRL_I→VI、OUTP/OUTN→原线、EN2→原 pin、
  ENI0-2/ENP0-4→8 个新 pin 网

### 4.4 加 Xldo
- 放 `ldo_05` symbol（先给 ldo_05 建 symbol）：VDD→VDD、VIN→V1V 新 pin、
  VBG→VBG 新 pin、VBL→VBL 新 pin、VOUT→VDDC 网、VSS→VSS

### 4.5 新 pins（11 个，按字母序创建）
```
ENI0 ENI1 ENI2 ENP0 ENP1 ENP2 ENP3 ENP4 V1V VBG VBL   (全 input)
```
adpll_top 共 22 pin。**注意**：pin 名与网名冲突坑（"Pin name collides with net name"）——
打 pin 前确认同名 wire label 已删；层级边界端口错位坑——两侧（adpll_top symbol ↔
schematic）pin 序按字母序同步。

---

## 5. tb_adpll_top（加 11 个源）

| 源 | 类型 | 值 | 节点 |
|---|---|---|---|
| Vv1v | vsource | dc=1.0 | V1V |
| Vvbg | vsource | dc=0.5 | VBG |
| Vvbl | vsource | dc=0.7 | VBL |
| Veni0..Veni2, Venp0..Venp4 | vsource | dc=0（全开） | ENI*/ENP* |

Xpll pin 列表同步 22 口；**Iinj 预充电改 val1=−300u**（VI≈0.30，0.5V 核过渡区工作点）。

---

## 6. 验证总清单（每层）

1. schCheck (0 0)（浮空网=预期除外）
2. si 批量导出 → `tools/compare_semantic.py`（端子名级）对 `netlist/inc/vco_c.scs` /
   `ldo_05.scs` / `pll_step2_main_c.scs`
3. 最终：tb_adpll_top si 导出 + 4 行 ahdl_include → 300ns 冒烟 vs pll_step2_main_c.scs
   （预期：CKFB 严格 100.0M 锁定——VAR_I 恢复频率权威后的判决性指标）
4. 波形存档服务器 /home/mei/sim/adpll_ted_smoke_300ns/ 同款流程
