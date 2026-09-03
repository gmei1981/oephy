# SS-BB-ADPLL 重构计划（ref2: Ye et al., CSTIC 2025, TSMC 40nm, 10.2-14.82GHz）

更新时间: 2026-09-03
暂停点: wp5_1u 350ns 已 SIGSTOP（数据保留，SIGCONT 可恢复，不占 CPU）

## 0. ref2 论文要点与决策记录

论文架构（SS-BB-ADPLL）:
- REF(100M) → 两级 DTC 延迟 → BBPD（亚采样 bang-bang，替代 TDC）
- BBPD ±1 → PI 数字环路滤波器（DLF）→ **双 DAC 分级调频**（一级宽范围 + 二级窄范围）
- 振荡器输出 **÷4** → 反馈到 BBPD（固定分频比，divider-based 亚采样）
- AFC 辅助锁定；GS（Gear Shifting）按 BBPD_DZ 死区判定锁定后逐级降低 kp/ki
- 实测: 196.8fs RMS（整数）/ 707.7fs（分数）@ 100M 参考

用户约束映射:
| 用户要求 | 落实 |
|---|---|
| VCO 用目前的，改单核 | vco_dual_8g_c → 保留 vco_x_c 单核（0.5V + Ls + CF 组），删核 B/EN2/耦合开关 |
| DAC 用理想 DAC | 新增理想 VA DAC ×2（粗/细），直接驱动变容管 bulk（替代 EN+NMOS 开关） |
| DTC 用目前架构 | dtc_10b 1023 开关单元 + 内嵌解码器保留，端口简化、解码逻辑改为相位累加器码 |
| 其它模块参考论文 | BBPD / PI DLF / AFC / GS / ÷4 全部新增 VA 行为模块 |

## 1. 新架构信号流

```
REF(100M) ──► DTC(现有1023单元) ──► CKR ──► BBPD(亚采样bang-bang) ──► PI DLF(kp/ki)
                                              ▲                              │
                                              │ DIV4                          ▼
                              ┌── ÷4 ─────────┘                     双理想DAC(粗7b/细9b)
                              │                                             │
                              ▼                                      VC1 ──► C1大varactor
                        VCO(现有单核0.5V) ◄─────────────────────────── VC2 ──► C2小varactor
                              ▲
                              └─ AFC: DIV4 沿计数 → 粗码基址（替代 Iinj 预充）
GS: BBPD_DZ(死区版)全零 + BB 均值≈0 持续 K 周期 → 锁定判定 → kp/ki 降档
分数通道: 相位累加器 acc+=FCW (mod 1024) → DTC CODE（DTC 范围 337ps > TVCO 125ps ✓）
```

## 2. 模块映射表

| 论文模块 | 现行资产 | 动作 |
|---|---|---|
| 双核 DCO | vco_dual_8g_c (Xa/Xb) | 改: 单核化，删 Xb/EN2/MSWP/MSWN/MPWRB |
| 变容管阵列 C1-C4 | VAR_I/VAR_P + NMOS 开关(68个) | 改: 删全部开关与 1G bleeder，DAC 直驱 bulk（复用 Plan C 已验证结论: 0.5V 核直连大 moscap KVCO=206MHz/V 单调） |
| 两级 DTC | dtc_10b 单级 | 保留单级（337ps 全范围 > 125ps 需求，记录偏差）；删 LMS 端口；内嵌解码器改 10b 码直通 |
| BBPD | 无（spd_x/cmp_x 是模拟采样 PD） | 新增 VA pll_bbpd.va |
| PI DLF | 无（gm_x 模拟积分） | 新增 VA pll_dlf.va |
| 双 DAC | 无（EN 数字码直控） | 新增理想 VA pll_dac.va ×2 |
| AFC | 无（Iinj 预充） | 新增 VA pll_afc.va |
| GS | 无（LMS 四路校准） | 新增 VA pll_gs.va |
| ÷4 | pll_mmd_edge（分数 MMD） | 新增 VA pll_div4.va；MMD 移出顶层 |

**从顶层删除**: Xspd Xcmp Xgm、Esumrst/Einv/Vrstofs、Xclkl Xlms、Xmmd、Iinj、Xci、Edbl（REF 直连 DTC）、Minvbuf 链（÷4 前只留一级缓冲）
**保留**: Xldo（ldo_05）、偏置源（VBG/VBL/V1V）、VDD/VSS/REF 源
**文件动作**: spd_cmp_gm.scs / pll_lms.va / pll_mmd_edge.va / pll_hybrid_aux.va 移出顶层 include（文件保留存档）

## 3. 各模块详细设计

### 3.1 VCO 单核 + DAC 直驱（gen_vco_c.py 改造，生成 vco_c_dac.scs）
- subckt `vco_x_c_dac (VDD VDDC VSS OUTP OUTN VC1 VC2)`——删 VCTRL_P/VCTRL_I/ENI0-2/ENP0-4/EN2
- C1 粗调: 大 moscap_rf nfin=24（wr=538n 同 cell，PLUS=OUTP/OUTN 各一，bulk←VC1），KVCO≈206MHz/V
- C2 细调: 小 moscap_rf nfin=2，bulk←VC2，KVCO≈5-20MHz/V（标定后定）
- 保留: 核管/交叉耦合对 nf=16、Ls=2n、CF 组 nr=174（变容管负载变化 → CF 重新标定，中心目标 8.0G）、缓冲
- 注意: DAC 是理想电压源直驱，无 wp4/wp5 的开关阈值问题、无 1G bleeder 浮空

### 3.2 理想 DAC（新 VA pll_dac.va）
- 端口 `(code[0:n-1] out ref)`, 参数 nbits/vmin=0/vmax=0.5/tr=1n
- out = vmin + code×(vmax-vmin)/2^n，阶梯间 1ns 平滑过渡（防 LTE 松弛，沿用 wp 经验）
- DAC1 粗: 7bit，LSB 3.9mV → ~0.8MHz/LSB，全量程 ~100MHz
- DAC2 细: 9bit，LSB ~1mV → ~0.01-0.02MHz/LSB（KVCO 5-20MHz/V）
- **决策点 A**: DLF 16bit 输出的分级映射——默认方案: 高 7 位→DAC1（基址由 AFC 装载）、低 9 位→DAC2；备选: ki 路径→粗 DAC、kp 路径→细 DAC

### 3.3 BBPD（新 VA pll_bbpd.va）
- 端口 `(ckr div4 bb bb_dz)`, 参数 Tdz=50p
- 每个 ckr 上升沿: 取最近的 div4 沿，Δt=div4沿−ckr沿；Δt>0 → bb=+1（加速），Δt<0 → bb=−1
- |Δt|<Tdz 时 bb_dz=0，否则 bb_dz=1（供 GS 锁定判定）；bb 主输出无死区
- 亚采样折叠防护: 只与最近沿比较（AFC 保证最近沿即目标沿）

### 3.4 PI DLF（新 VA pll_dlf.va）
- 端口 `(ckr bb afc_code[6:0] code[15:0])`, 参数 kp=8/ki=1（初值，GS 可改）
- 每 ckr 沿: acc += ki×bb; code = acc + kp×bb；AFC 完成时装载基址 acc=afc_code<<9
- 限幅 ±2^15，输出 code[15:0]；高 7 位接 DAC1 码、低 9 位接 DAC2 码

### 3.5 AFC（新 VA pll_afc.va）
- 端口 `(ref div4 afc_code[6:0] afc_done)`, 参数 target=20（8G/4/100M）
- 每个 REF 窗口计数 div4 沿: 偏少 → afc_code+1，偏多 → −1，命中 → 保持
- 连续 2 个窗口命中 → afc_done=1 → DLF 装载基址、GS 启动；±1 粗步 ≈0.8MHz×20...（注意粗步与命中判据按标定 KVCO 复核）
- 决策点 B: AFC 步进粒度（单步 1 LSB ≈0.8MHz 时 div4 沿计数分辨率 100M 窗口 = 1 沿/周期 ≈ 400MHz 分辨率——AFC 用多窗口平均或直接粗步进+BB 相位象限检查）

### 3.6 GS（新 VA pll_gs.va）
- 端口 `(ref bb bb_dz afc_done kp_out ki_out gear[2:0])`
- 窗口 W=128 个 REF 周期: bb_dz 全零 且 |Σbb|≤2 → 锁定判定 → gear+1，kp/ki 减半
- 三档: (kp=8,ki=1) → (4,0.5) → (2,0.25)；gear 满档停止；未锁定判定（bb_dz 持续非零）可回档

### 3.7 ÷4（新 VA pll_div4.va）
- 端口 `(in out)`, 参数 vth=0.5；对 in 上升沿计数，每 4 沿翻转 out
- 输入接 OUTP（保留一级 buffer，防 25.10 混搭发散历史坑——全 scs 闭环则直连可试）

### 3.8 DTC 改造（tools/gen_dtc_ref.py 变体）
- 端口: `(CK2X CKDTCD VDD VSS CODE[9:0])`——删 CKFB/KDTC/EPSC/SEL/ALT/VDCC/RDCC
- 内嵌解码器: 10b CODE → 1023 使能直通（现 pll_dtc_decoder_10b.va 的 Wu-QE 逻辑废弃，保留文件存档）
- 保留: R0 rhim 2.3µ×2µ、CKXB 反相器、MRST_D 复位管、1023×(NMOS 开关 nf=2 + CLSB=0.5fF)、transition 50p

### 3.9 相位累加器（新 VA pll_frac_acc.va，分数通道用）
- 端口 `(ref code[9:0])`, 参数 FCW；acc += FCW (mod 1024)，code = acc
- 整数通道 FCW=0 → code 恒 0（固定延迟 0，BBPD 直接比对）
- 分数通道 FCW = frac×1024（8.05G/100M → N=80.5 → frac=0.5 → FCW=512；决策点 C: 分数通道选 8.05G 还是沿用 step1 153.6M/6.2G）

## 4. 顶层组装（新 sim/pll_ssbb_main.scs）

```
Vvdd/Vvss/Vref(100M pulse 0-0.8)  Xldo(VDD V1V VBG VBL VDDC VSS) ldo_05
Xdtc (REF CKDTCD VDD VSS CODE[9:0]) dtc_10b_ss        // REF 直连，无 Edbl
Xbbpd (CKDTCD DIV4 BB BB_DZ) pll_bbpd Tdz=50p
Xdlf  (CKDTCD BB AFC_CODE CODE[15:0]) pll_dlf kp=8 ki=1
Xdac1 (CODE[15:9] VC1 VSS) pll_dac nbits=7 vmax=0.5   // 粗
Xdac2 (CODE[8:0]  VC2 VSS) pll_dac nbits=9 vmax=0.5   // 细
Xvco  (VDD VDDC VSS OUTP OUTN VC1 VC2) vco_x_c_dac    // 单核
Xdiv4 (OUTPB DIV4) pll_div4 vth=0.5
Xafc  (REF DIV4 AFC_CODE AFC_DONE) pll_afc target=20
Xgs   (REF BB BB_DZ AFC_DONE KP KI GEAR) pll_gs       // kp/ki 以参数重设或端口直改
Xacc  (REF CODE[9:0]) pll_frac_acc FCW=0              // 整数首版；分数版 FCW=512
（OUTP→buffer→OUTPB 一级；保存: REF CKR BB BB_DZ CODE VC1 VC2 DIV4 OUTP VDDC AFC_CODE GEAR）
```

## 5. 验证计划（分阶段，每阶段 0 错误 + 判据记录）

- **V1 VA 单测**: bbpd（合成 ckr/div4 扫 Δt → bb/bb_dz 翻转点）、dlf（bb 脉冲串 → code 台阶）、dac（码 → 电压阶梯）、afc（div4 频率台阶 → 码收敛）、div4（8G 正弦 → 2G 方波）、gs（bb_dz 置零 → 换档）
- **V2 开环链**: REF→DTC→BBPD 扫 CODE 看 bb 翻转；÷4 沿计数核对
- **V3 AFC 收敛**: 闭环网表只开 AFC（DLF 冻结），fVCO 拉入 ±1 粗步
- **V4 整数闭环**（100M/8G）: 锁定判据 = fVCO 8.0G±0.1%、BB 均值≈0、BB_DZ 持续零、GS 换档完成；周期抖动（jitter_analyze.py 复用）
- **V5 分数通道**: FCW→杂散（spur_analyze.py 复用）、抖动
- **V6 对比论文**: 196.8fs int / 707.7fs frac @12G/100M 口径；本项目 8G/100M 注明口径差异

## 6. 风险与对策

| 风险 | 对策 |
|---|---|
| BBPD bang-bang 环极限环（wp 系列老问题） | 死区观察 + GS 降档；必要时 DLF 加 dithering |
| DAC LSB 量化粗于细调需求 | C2 尺寸/KVCO 标定后复核；DAC2 提到 10bit 兜底 |
| moscap C-V 台阶（Plan C 教训） | DAC 输出限幅在工作区 0.2-0.5V（单调段）；直连大 moscap 已验证 |
| 亚采样相位折叠: AFC 粗对准不足 → bb 无方向 | AFC 命中判据加相位象限检查；V2 开环先验 bb 方向性 |
| 25.10 服务器混搭发散（历史坑） | 全 scs 闭环跑服务器；原理图侧后置 |
| DAC 阶梯毛刺 → VCO 供电/幅度调制 | DAC 输出 1ns 平滑 + 观察 VDDC 纹波 |

## 7. 仿真执行

- 本机 20.1: VA 单测 + 短闭环（60-300ns）；服务器 25.10: 长闭环（1-10µs, +preset=ax +mt）
- 预期提速: 顶层删 spd/cmp/gm/LMS/MMD 与 68 开关管；dtc_10b 2053 实例仍是最大块 → 速率应优于 wp5 的 9.7ns/min
- 执行顺序: 本机闭环锁上后再上服务器长跑

## 8. 原理图侧（后置）

- 老 cells（spd_x/cmp_x/gm_x/tb 系列）不再使用；adpll_top 待网表闭环后重画（VA symbol ×7 + dtc_10b_ss + vco 单核 + ldo）
- 沿用既有桥批量绘制管线（tools/build_*.py），netlist-to-virtuoso-schematic 流程不变

## 9. 待用户确认的决策点

- A: 双 DAC 分级映射（默认: 高 7 位粗/低 9 位细）
- B: AFC 步进/命中判据精度（默认: ±1 粗步 + 双窗口确认）
- C: 分数通道选择（默认: 8.05G/100M, FCW=512；备选 153.6M/6.2G 旧通道）
- D: wp5_1u 暂停的 350ns 跑：保留（SIGCONT 恢复）还是终止释放（默认: 保留）
