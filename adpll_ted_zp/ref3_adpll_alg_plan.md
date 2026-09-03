# ADPLL_ALG（ref3 内部算法方案 V1.00, 2026/06/10）架构改造计划

更新时间: 2026-09-03（决策点 A-E 已按默认执行；V0 完成：14 模块编译 0 错误；V1 完成：22 台 TB/42 项判定全绿；V2 完成：12 台 TB/12 项判定全绿，标定常数 tdc_norm_coef=1/64、KVCO_A=0.607MHz/LSB、8.0G@Abank≈339、kdtc0≈353——见 progress.md 同日条目）
前置状态: ref2 SS-BB-ADPLL V0-V4 已完成（V4 1.2µs 9/9 PASS，10µs 服务器长跑中）——ref3 启动后 ref2 线封存留作对照

## 0. ref3 要点与决策记录

ref3 架构（MMD 分频反馈型 ADPLL，"counter-assisted + TDC + DTC 预测"）:
- 指标: fref=25MHz，输出 4800~5200MHz，DCO 步长 50kHz，锁定 200µs，RMS jitter <200fs
- 环路: REF→(可选×2倍频器+DCC)→DTC(10b，增益后台校准) 与 DCO→MMD(÷4~8191)→TDC(模拟 CTDC×2+FTDC) 鉴相
- 反馈 DSM: MASH 1/2/3 阶可选 + LFSR dither + 近整数模式，输出 freq_div_ratio(13b)、q_err(s,36,35)、
  sel_clk_fb（DCO 升/降沿切换 = 半周期量化，与 JSSC 论文范围减半同源）
- DCO 控制: LPF 输出 ctrl_out → Abank_code(9b 整数) + lpf_frac(26b 小数) → DCO DSM → 4b 温度计 dither
- 三路后台校准: K_DTC（phe×q_err）、参考倍频 DCC（奇偶周期）、DCO 占空比（sel_clk_fb）→ dco_dtc_comp
- 五状态 FSM: IDEL→AFC→FLL→PLL→LOCK→(UNLOCK→FLL)；Lock Detect 双门限 2^N 连续计数
- 数字口径全部 (u/s,M,N) 定点（本计划 VA 用 real 行为实现，关键处显式 floor/rnd/sat/LMT）

与 ref2 现状的本质差异（改造工作量从大到小）:
| # | 差异 | ref2 现状 | ref3 要求 |
|---|---|---|---|
| 1 | 鉴相 | BBPD 1-bit bang-bang | TDC 多 bit（模拟 CTDC/FTDC + 数字解码归一化 phe s,18,16） |
| 2 | 反馈 | 固定 ÷4 | MMD ÷4~8191 + 反馈 DSM（多阶/dither/近整数/q_err/sel_clk_fb） |
| 3 | DCO 控制 | DLF 16b→双 DAC 连续 | LPF int/frac 拆分：Abank 9b + DCO DSM 4b 温度计 dither |
| 4 | 锁定流程 | AFC→DLF 从动拉入 | FSM 五状态 + FLL 频率锁定级 + Lock Detect |
| 5 | 校准 | 无（LMS 已随 ref2 删除） | 三路后台校准（多 bit phe 口径，非 sign-LMS） |

## 1. 新架构信号流

```
REF(100M*) ─►(×2倍频器+DCC, 可关)─► DTC(现有1023单元) ──────────► CKR
                                     ▲ dtc_code(10b)               │
                                     │ = f(q_err, kdtc, offset,     ▼
                                     │     dco_dtc_comp)      TDC(VA行为: CTDC×2+FTDC+arb)
                                     │                              │ ctdc_out_a/b, ftdc_out, arb_out
                                     │                              ▼
FCW(u,48,35) ─► 反馈DSM(MASH1/2/3 ──► PFD: 解码+拼位 tdc_code(9b)×tdc_norm_coef
                +dither+近整数)         −phe_sh → sat → phe(s,18,16)
                │    │    │                    ├─► LPF(kp1/2,ki1/2, freq_ctrl装载)
     freq_div_ratio  q_err  sel_clk_fb          │      ├─ Abank_code(9b) ──► DCO A路(粗)
                │                                    └─ lpf_frac(26b) ─► DCO DSM ─► Fbank(4b thermo) ──► DCO F路(细)
                ▼                                                                       ▲
             MMD(÷4~8191, P/S计数器) ◄── DCO(单核0.5V, 8G*) ◄── Pbank(6b, AFC) ────────┘
                │                    ▲
                └─► CKMMD ─► TDC     └─ FLL: 窗口计数频差 → Abank 积分 → freq_ctrl(LP初值) + freq_lock
三路校准(后台): kdtc(phe×q_err) / refDCC(奇偶周期×phe) / dcoDCC(sel_clk_fb×phe)
FSM: IDEL→AFC→FLL→PLL→LOCK→UNLOCK；LockDetect: |phe|双门限+2^N连续 → phase_lock
*  载频决策点 A：默认先用现有 8G/100M 硬件验证算法（阶段A），25M/4.8-5.2G 真口径后置（阶段B）
```

## 2. 模块映射表

| ref3 模块（图号） | 接口/位宽 | 现行资产 | 动作 |
|---|---|---|---|
| Pbank 校准（图2-4） | pbank_code u,6,0；窗 2^afc_ref_cnt_thr；fb_cnt u,14,0；afc_freq_err s,15,0；最小误差记录 | pll_afc.va（7b 二分+skipwins+再武装） | **改造**: 6b 码、窗口 2^thr 参数化、加"最小误差控制位"记录（图4 流程）、AFC 期间配合 Abank=256 中值（LPF cfg 模式） |
| ADPLL FSM（图5） | fsm_state u,3,0；afc_finish/freq_lock/phase_lock 输入 | 无 | **新增** pll_fsm.va |
| MMD（图6-7） | freq_div_ratio u,13,0（[1:0]→ps_ctrl，[12:2]→Pcount 11b）；÷4~8191 | pll_mmd_edge.va（双沿计数+SEL 半周期已验证） | **重构**: 真接收 freq_div_ratio，P/S 计数器（Pcount 11b+Scount 1b，P≤1 降 2），sel_clk_fb 控制输出沿选择；DSM 拆出 |
| 反馈 DSM（图8-9） | accum1/2/3 u,36,35；yout1(1b)/yout2(s,3,0)/yout3(s,4,0)；dsm_out_fb s,4,0；q_err s,36,35；dsm_half s,4,1；fcw[34:0] | pll_mmd_edge.va 内嵌 MASH1-1 + pll_frac_acc.va | **新增** pll_dsm_fb.va（MASH1-1-1，mode 选阶；q_err/dsm_half/sel_clk_fb 输出） |
| Dither+近整数（图9-10） | 10b LFSR 复位全1；near_integer_mode→fcw_prbs→fcw_dither u,1,1 | 无 | **并入** pll_dsm_fb.va（LFSR 函数复用） |
| DCO 控制 DSM（图10-11） | accum1/2/3 u,27,26；lpf_frac u,26,26→dsm_out_dco u,3,0（thermo）；clk_ref→clk_dsm 域 | pll_dac7/9.va（DAC 无 DSM） | **新增** pll_dsm_dco.va（MASH 同构，输出 4b 温度计） |
| FLL（图12） | freq_ref_cnt u,12,0（2^thr 窗）；fb_cnt u,16,0；fll_freq_err s,17,0；freq_ctrl s,25,15（步长 1/2^freq_lock_step=1/128）；freq_lock | 无 | **新增** pll_fll.va |
| PFD/TDC（图13） | ctdc_out_a/b u,16,0（one-hot 回送 ctdc_in_one_hot_a/b）、ftdc_out u,16,0、arb_out；decoder_out_sign/high/low 拼位 tdc_code u,9,0；×tdc_norm_coef(1.2/200) −phe_sh(0.5)→sat6→phe s,18,16 | 无（BBPD 1b） | **新增**: VA 行为 TDC（有限分辨率+可注噪）+ pll_pfd.va（LUT/解码/归一化）；晶体管 TDC 后置（决策点 B） |
| LPF（图14） | kp1/kp2(u,18,8) ki1/ki2(u,20,10) phase_lock 切换；freq_ctrl s,25,15 装载；ctrl_out s,36,26；Abank_code u,9,0 LMT0~511（cfg 开环模式 256）；lpf_frac u,26,26 | pll_dlf.va（PI+AFC 从动+基址装载） | **改造**: 从动模式泛化（AFC 码/FLL freq_ctrl 两级交接）、int/frac 拆分输出、kp/ki 双档（LockDetect 驱动）、cfg 模式 |
| DTC 增益校准（图15） | kdtc s,34,24（积分，右移 step）；multi_out=phe×q_err s,54,51→rnd59→右移；dtc_code u,10,0 = kdtc×(q_err+offset)→rnd→LMT；dco_dtc_comp s,6,0 相加 | pll_lms.va kdtc 路（1b ebit×epsc sign-LMS） | **新增** pll_cal_kdtc.va（多 bit 乘法口径，非 sign-LMS） |
| 参考倍频 DCC（图16） | even_cycle 翻转；phe 奇偶选通→freq_err 积分 s,19,16→右移 step6→ref_calib_coef s,37,31（送 DSM 补偿）；ref_sel/ref_double_en | pll_lms.va rdcc 路 + pll_doubler_edge.va（老库） | **新增** pll_cal_refdcc.va；倍频器复用 doubler |
| DCO 占空比校准（图17） | phe×(sel_clk_fb−psel) 选通→积分→dco_calib_coef s,37,31→rnd31→dco_dtc_comp s,6,0 | pll_lms.va vdcc 路 | **新增** pll_cal_dcodcc.va |
| Lock Detect（图18） | |phe|≤lock_phe_thr(655) 连续 2^lock_cnt_thr(8) → phase_lock=1；≥unlock_phe_thr(6554) 连续 2^unlock_cnt_thr → 0 | pll_gs.va（bb_dz 口径，退役） | **新增** pll_lockdet.va |
| DTC 10b | dtc_code u,10,0 | dtc_10b_ss（1023 单元，τ_r 0.354ps/LSB 全范围 362ps） | **复用**（8G: TVCO/2=62.5ps ≪ 362ps ✓；10b 端口直接对接） |
| DCO P/A/F bank | Pbank 6b / Abank 9b / Fbank 4b thermo；50kHz 步长 | vco_c_dac（DAC1 7b 2.4MHz/LSB + DAC2 9b 55kHz/LSB，KVCO1=621M/V、KVCO2=57M/V 已标定） | **阶段A 映射**: Abank↦DAC1（扩 9b，pll_dac7→pll_dac9b 复制改）、Fbank↦DAC2 低 4b 由 DSM dither（55k/16≈3.4kHz 有效步长）；Pbank↦DAC1 高位子集或 CF 组改造（决策点 C）；**阶段B**: 5G retune 真电容 bank |
| 顶层组装 | — | tools/gen_ssbb_top.py | **新增** tools/gen_ref3_top.py（沿用单行 save、include 顺序等已沉淀规范） |

**退役（移出顶层，文件存档）**: pll_bbpd/pll_gs/pll_frac_acc/pll_div4/pll_dac7/pll_dac9
**保留**: ldo_05、偏置源、vco 单核、dtc_10b_ss、（老库）pll_doubler_edge/pll_dtc_decoder_10b

## 3. 各模块详细设计（端口按本仓库 VA 惯例：独立端口+展开赋值，0.8V 逻辑，vth=0.4）

### 3.1 pll_dsm_fb.va（反馈 DSM，图8-10）
- 输入: fcw 整数/分数（real 参数 FCW，如 200.0 或 80.5）；参数 dsm_fb_mode(0/1/2)、dither_fb_en、near_integer_mode
- MASH1-1-1: accum1 += fcw[34:0]; yout1=carry; accum2 += frac(accum1); yout2=…; 累加器 36b、输出 yout3(s,4,0)
- dsm_out_fb = yout1+yout2+yout3−const（mode 选阶）；freq_div_ratio = floor(FCW>>1) + dsm_half（s,4,1 → ps_ctrl 用 [1:0]）
- q_err s,36,35 = 累加器残差组合（供 kdtc 校准与 DTC 预测）
- sel_clk_fb = dsm_out 半周期选择（延迟 Z^-n 补偿 MMD 电路延迟，参数可配）
- 近整数模式: fcw_prbs(LFSR10)→fcw_dither(±0.5LSB) 加到 FCW 尾数；dither 同源 LFSR
- 时钟域: clk_ref 沿更新

### 3.2 MMD 重构（pll_mmd_edge.va → 保留文件，新 pll_mmd_ps.va，图6-7）
- 输入: vco_in（模拟）、p0..p12（freq_div_ratio 13b 数字）；输出 ckfb、sel 用法变化
- [1:0]→Scount(1b)+切换、[12:2]→Pcount(11b)；Pcount 从 N_INT(n) 递减，≤1 置 flag；Scount==0 置 flag
- 输出沿选择由 sel_clk_fb 控制（升沿/降沿重定时 = 半周期相移，机制已在 pll_mmd_edge 验证）
- ÷4 下限: P/S 结构保证 4~8191 全覆盖（ps_ctrl 逻辑: ratio<8 时的切换路径，图7）

### 3.3 VA 行为 TDC + pll_pfd.va（图13）
- 行为 TDC（新 pll_tdc_beh.va，决策点 B 的阶段A 形态）: 输入 CKR/CKMMD 模拟沿，输出
  ctdc_out_a/b(温度计，按粗 bin)、ftdc_out(细 bin)、arb_out(方向)；bin 宽参数化（粗=1 个 VCO 周期/16，细=粗/16，
  总分辨率先按 ~1ps 级设计，与 tdc_norm_coef 联调）；one_hot 回送口按 LUT 表实现（死区也送 interval 1000…0）
- pll_pfd.va: decoder_a/b（0000→0, 1000→1, 1100→2, … 全1→15）+ decoder_out_high/low/sign 拼位 → tdc_code u,9,0
  → ×tdc_norm_coef −phe_sh → sat6 → phe_out（real 输出，1V=1.0 归一化相位，锁定点 0.5）
- phe_inv_en 取反使能

### 3.4 pll_fll.va（图12）
- 窗口 2^freq_ref_cnt_thr（默认 thr=9 → 512 参考周期）计 CKMMD 沿 → fb_cnt u,16,0（clk_dsm 域）
- calc_cnt = floor(FCW×2^thr 尾数折算)；fll_freq_err = fb_cnt_reg − calc_cnt（s,17,0）
- 积分器: err×(1/2^freq_lock_step=1/128) 累加 → freq_ctrl s,25,15；|err|≤freq_lock_thr(0) → freq_lock=1
- FLL 期间 freq_ctrl 经 LPF cfg/从动通道驱动 Abank（与 ref2 V4 "DLF 从动 AFC" 同构，交接无缝）

### 3.5 LPF 改造（pll_dlf.va → pll_lpf.va，图14）
- 输入 phe（real）；kp/ki 由 phase_lock 双档切换（kp1/kp2、ki1/ki2 参数）
- 三级交接: AFC 期间从动 pbank 码（Abank=256 中值 by cfg）；FLL 期间装载/跟踪 freq_ctrl；freq_lock 后 bb→phe 闭环
- ctrl_out s,36,26 = kp_out + 积分；取整 → Abank_code u,9,0 LMT 0~511；取小数 → lpf_frac u,26,26
- afc_finish/freq_lock 门控沿（沿用 ref2 无缝交接经验）

### 3.6 pll_dsm_dco.va（图11-12）
- lpf_frac 26b 累加器组（u,27,26），MASH 选阶，dsm_out_dco u,3,0 → 15 单元温度计展开
- clk_dsm 域（=clk_ref 或分频，参数化）；dither_dco_en
- 输出 4b thermo → DAC2 低 4 位码（阶段A）

### 3.7 三路校准（pll_cal_kdtc / pll_cal_refdcc / pll_cal_dcodcc.va，图15-17）
- kdtc: multi_out = phe×(q_err+offset(u,35,35, 默认 0.5；倍频时 0.25)) → rnd → 右移 kdtc_calib_step → 积分 kdtc s,34,24；
  dtc_code = kdtc×(q_err+offset) → rnd → LMT 0~511（10b）+ dco_dtc_comp(s,6,0) 相加补偿
- refdcc: even_cycle 每 REF 周期翻转；phe 奇偶选通±1 → 积分 → 右移 step(6) → ref_calib_coef s,37,31 → 送反馈 DSM 补偿
- dcodcc: phe×(sel_clk_fb−psel) 选通 → 积分 → dco_calib_coef s,37,31 → rnd31 → dco_dtc_comp s,6,0
- 步长/方向/使能参数与 spec 默认值一致（step=0/6/2，en 默认 kdtc=1、dco=1）

### 3.8 pll_lockdet.va + pll_fsm.va（图5/18）
- lockdet: |phe|≤655(锁) 连续 256 → phase_lock=1；≥6554(失锁) 连续 256 → 0；计数器清零语义按 spec
- fsm: IDEL(复位)→AFC(开环 cfg=256、dsm_dco_en=0、afc_calib_en)→FLL(freq_lock_en)→PLL(释放 rstn_dsm_fb/mmd/lpf/calib/lock，
  按使能开三校准)→LOCK(phase_lock 监视)→UNLOCK→FLL；fsm_state u,3,0 输出
- ref2 的 AFC/DLF 交接经验（从动模式、skipwins、再武装）全部继承到 FSM 时序

### 3.9 DCO/载频（决策点 A/C）
- 阶段A（默认）: 现有 8G/100M 硬件。Abank↦DAC1 扩 9b（LSB 2.4M→1.2MHz/LSB，量程 0.5V/512）；
  Fbank↦DAC2 低 4b dither（55k/16≈3.4kHz 有效步，优于 50kHz spec ✓）；Pbank 阶段A 暂用 Abank 高位兼
  （真 Pbank 电容组在阶段B 落地）；FCW 口径 8G/100M → N=80（整数）/80.5（分数）
- 阶段B: 4.8-5.2G retune（CF 组重标：C 需 ×(8/5)²≈2.56 → 加电容或改电感）+ Pbank 6b 二进制交叠子带 + Fbank 15 单元真 thermo 电容

## 4. 顶层组装（新 tools/gen_ref3_top.py → sim/pll_ref3_main.scs）

```
Vvdd/Vvss/Vref(100M pulse)  Xldo(...)  Xvco(vco_x_c_dac: VC1←DACab, VC2←DACfb)
Xdtc  (REF CKDTCD VDD VSS dtc0..dtc9) dtc_10b_ss          // dtc_code 来自 cal_kdtc
Xtdc  (CKDTCD CKMMD ctdc_a[16]/ctdc_b[16]/ftdc[16] arb onehot_a/b) pll_tdc_beh
Xpfd  (ctdc/ftdc/arb → phe) pll_pfd
Xlpf  (phe freq_ctrl fsm 门控 → ab0..ab8, fr0..fr25) pll_lpf
Xdacab(ab0..ab8 → VC1) pll_dac9b                            // Abank 9b
Xdsmf (REF FCW → p0..p12, q_err, selclkfb, refcalibcomp) pll_dsm_fb
Xmmd  (OUTP p0..p12 selclkfb → CKMMD) pll_mmd_ps
Xdsmd (REF fr0..fr25 → f0..f3 thermo) pll_dsm_dco
Xdacfb(f0..f3 → VC2 低4b) pll_dac9(改接线)
Xfll  (REF CKMMD → freq_ctrl freq_lock) pll_fll
Xafc  (REF CKMMD → pb0..pb5 afc_finish) pll_afc(6b 改版)
Xcalk/Xcalr/Xcald (phe q_err selclkfb → dtc_code/ref_coef/dco_comp) ×3
Xlock (phe → phase_lock) pll_lockdet
Xfsm  (afc_finish freq_lock phase_lock → fsm_state 各 rstn/en) pll_fsm
保存: REF CKDTCD CKMMD phe ab/fr 码 VC1 VC2 OUTP VDDC fsm_state freq_ctrl kdtc phase_lock …(单行 save)
```

## 5. 验证计划（沿用 V 分级，每级 0 错误+判据入 progress.md）

- **R1=V0**: 全部新 VA + 改造 VA 落地，ahdlcmi 本机编译 0 错误（沿用: 显式 electrical、折行、transition 顶层、
  实例参数覆盖陷阱自查）
- **R2=V1 单测**: dsm_fb（FCW 扫 → freq_div_ratio 均值/抖动、q_err 幅度、阶数切换、dither/近整数频谱）、
  mmd_ps（ratio 4~8191 扫 6 点 + sel_clk_fb 半周期相移）、tdc_beh+pfd（Δt 扫 → phe 线性度/斜率/死区、LUT 回送）、
  fll（频差台阶 → freq_ctrl 收敛+freq_lock）、lpf（phe 阶跃 → Abank/frac、三级交接无跳变）、dsm_dco（frac 扫 →
  thermo 占空比）、afc6b（含最小误差记录路径）、三校准（注入已知增益误差 → 收敛到真值）、lockdet/fsm（全状态跳转）
- **R3=V2 开环标定**: TDC 实测 bin→tdc_norm_coef 定标；DTC τ_r 复标（0.354ps/LSB）→ dtc_offset/kdtc 初值；
  Abank KVCO 复核（9b DAC1）；FCW=80 整数通道链路（REF→DTC→TDC→phe 摆度）
- **R4=V3 整数闭环**: FSM 全流程 AFC→FLL→PLL→LOCK（判据: pbank 二分轨迹、freq_lock、phe→0.5±门限、
  phase_lock、fVCO 8.0G±0.1%、Abank/frac 无缝交接无跳变）
- **R5=V4 分数闭环**: FCW=80.5（或近整数 80.001）+ 三校准全开 → 杂散/抖动（jitter_analyze/spur_analyze 复用，
  采样口径按 DLF 消费点逐周期，沿用 V4 教训）+ 服务器长跑 10µs+
- **R6=V5 阶段B（可选）**: 5G/25M 真口径 retune + 真 P/F bank + 200µs 锁定窗（VA 纯数字快仿 + 晶体管缩放窗）

## 6. 风险与对策

| 风险 | 对策 |
|---|---|
| TDC 行为模型分辨率/噪声与真模拟不符 → 校准收敛结论失真 | bin 宽参数化扫描 + 可注噪开关；晶体管 TDC 列为阶段B |
| MMD 8G 输入 + P/S 计数器 VA 事件风暴（每 VCO 沿都触发） | 沿用 pll_mmd_edge 的沿计数技巧；ratio≥8 时输出翻转才产生对外事件 |
| 26b lpf_frac + MASH 高阶在 real 实现下数值精度 | 定点位宽按 spec 截断/rnd 显式建模；V1 单测对拍 MATLAB/手算 |
| 200µs 锁定窗晶体管级不可仿 | 阶段A 缩放（大 step/短窗）验证机制；真口径留 VA 快仿 |
| 多模块同沿事件序歧义（ref2/pll_lms 老坑） | 各模块错沿采样（上升沿算、下降沿取的惯例延续）；V1 单测覆盖同沿场景 |
| dtc_10b 2053 实例仍是速率瓶颈 | 不变；lean save 单行；服务器 ax+mt |
| 8G/100M 与 25M/5G 口径换算错误 | 常数表集中管理（新 scripts/ref3_consts.py），阶段A/B 共用换算函数 |

## 7. 仿真执行

- 本机 20.1: R1/R2 单测 + 短闭环；服务器 25.10: R4/R5 长跑（+preset=ax +mt=8）
- ref2 的 V4 10µs 服务器跑放完留档（BBPD 对照数据），不阻塞 ref3
- 进度记录: progress.md 追加 "ref3 ADPLL_ALG 改造" 章节沿用现行格式

## 8. 原理图侧（后置）

- netlist 闭环锁定后: 新 symbol 批量入库（沿用 tools/build_* 管线与 netlist-to-virtuoso-schematic 流程）
- 顶层重画：VA symbol ~12 + dtc_10b_ss + vco 单核 + ldo；老 BBPD/GS/div4 symbol 存档不删

## 9. 决策点（2026-09-03 用户确认，全部按默认执行）

- **A 载频口径** ✅: 阶段A 用现有 8G/100M 硬件验证算法，阶段B retune 25M/4.8-5.2G
- **B TDC 实现深度** ✅: VA 行为 TDC（bin 参数化+注噪）先行，晶体管 TDC 阶段B
- **C Pbank 阶段A 形态** ✅: Abank 高位兼任（6b×8 映射，记录与真 Pbank 差异）
- **D 校准默认开关** ✅: 按 spec（kdtc=1、dco=1、refdcc 随 ref_double_en=0 关闭）；分数通道验证时全开
- **E ref2 线处置** ✅: 封存（文件保留、10µs 跑完留档作 BBPD 对照）
