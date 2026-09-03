# 论文复现设计文档 — 14nm 超低抖动小数分频 PLL（JSSC 2021, Wu et al.）

> 目标：TSMC 12nm（CLN12FFC，0.8V 核心）晶体管级复现
> [A 14-nm Ultra-Low Jitter Fractional-N PLL Using a DTC Range Reduction Technique and a Reconfigurable Dual-Core VCO](https://doi.org/10.1109/JSSC.2021.3111134)
> 参考：`A_14-nm_Ultra-Low_Jitter_Fractional-N_PLL_Using_a_DTC_Range_Reduction_Technique_and_a_Reconfigurable_Dual-Core_VCO.pdf`
> 基础复用：`/home/gmei/git/oephy/adpll`（UCIe 6.2G 小数 DTC 采样 ADPLL，晶体管+VA 混合已验证）

## 0. 任务两步走

| 步骤 | f_ref | f_VCO | 说明 |
|---|---|---|---|
| Step 1（先不改频率） | 76.8 MHz（片内倍频→153.6 MHz DTC 采样率） | 6.2 GHz（=40.36458×153.6M） | 与论文 Fig.16(a) 相同通道，逐项比对 |
| Step 2 | 100 MHz | 8 GHz | N=80 整数通道，重推导全部参数 |

## 1. 论文关键指标（比对基准）

| 指标 | 论文值 | 备注 |
|---|---|---|
| 集成抖动 (10k–100M) | 83.4 fs 双核 / 96.3 fs 单核 | Fig.16(a), fvco=6.2G, 3.1G 输出 |
| 近整数通道抖动 | 94.3 fs（6451.3 MHz = 42×153.6M+100k） | Fig.16(b) |
| VCO PN @100kHz | −98.1 dBc/Hz 单核 → −101 dBc/Hz 双核（3G 输出） | Fig.15, 3 dB 改进 |
| DTC 分辨率 Tres | 330 fs（设计 350 fs） | 10-bit, DR=2^10×Tres≈320 ps |
| DTC INL | ≤1 LSB（范围减半后 4→1 LSB） | Fig.11(b) |
| 环路带宽 | 1.2 MHz | 相比 [16] 的 800 kHz 加宽 |
| 小数杂散 | < −70 dBc 近整数 | Fig.17/18(a) |
| 参考杂散 | −69.6 dBc 最差 | Fig.17 |
| FoM | −250.1 dB（双核 14.2 mW）/ −251.2 dB（单核 8.2 mW） | |
| 锁定/校准收敛 | 全部校准 <40 µs 收敛 | Fig.10(a)，初始误差：32mV 失调、10% K 误差、20ps VCO 占空比误差、57% 参考占空比 |
| 供电 | 模拟 1V，数字 0.8V，VCO 核 0.5V（LDO） | 14nm 薄栅器件可靠性 |

## 2. 架构（论文 Fig.6/7/9/11/12）

```
XO 76.8M ──→ 倍频器(×2) ──→ DTC(RC延迟核+反相缓冲,10bit) ──→ CKDTC ──→ SPD 斜坡触发
                                                                    │
CKVCO 6.2G ──→ ÷2/3 预分频 MMD (16-255) ──→ DFF1重定时(↑) ─┐       │
                              └────────────→ DFF2重定时(↓) ─┴→2:1mux─→ CKFB ─→ 采样 VHOLD(=Vsmp)
                              SEL_CKFB（DSM 1-bit 累加器延迟输出）     │
                                                                      ↓
    FCW ──×(右移1bit,×2)──→ MASH1-1 DSM ──÷(左移1bit,÷2)──→ [整数 | 分数位]
                                                                   比较器 e[k]
VHOLD ─┬─→ GM(0.5µS) → CI(2-62pF) → VCTRL_I ──→ VCO 积分变容管 KVCO_I
       └─→ VCTRL_P ──→ VCO 比例变容管 KVCO_P（SPD 高增益直接调 VCO）
       └─→ 比较器 → e[k] → 3×sign-LMS（K_DTC / CKREF DCC / VCO DCC）+ 比较器参考 1阶DSM
```

- **范围减半核心机制**：MMD 后加 DFF2 用 CKVCO 下降沿重定时，CKFB1 领先 CKFB2 半个 VCO 周期；
  SEL_CKFB 抖动 2:1 mux → 相位量化步长 TVCO/2，DTC 所需 DR 减半（MASH1-1 下 2×TVCO→1×TVCO）。
- **DSM 改造**：FCW 右移 1 位（×2）送常规 DSM，DSM 输出左移 1 位（÷2），分数位进 1-bit 累加器，
  延迟 Z^-n 后作 SEL_CKFB（补偿 MMD 电路延迟）。
- **类型-II 环**：Vsmp 直调 VCO（比例），GM+CI 积分路径；GM 小（0.5µS），CI=15pF@500kHz，可编程 2–62pF。
- **三个 sign-LMS**（共用 e[k]，不同 μ 保证稳定）：
  - K_DTC 增益校准：e[k] 与 DSM 累积 QE（ε 序列）相关
  - CKREF DCC：e[k] 与 ±1 交替（CKDTC 奇偶周期）相关
  - VCO DCC：e[k] 与 sign-extended SEL_CKFB 相关（补偿 VCO 占空比误差/DFF 失配的残余相位误差）
  - 比较器参考由一阶数字 DSM 动态调整跟踪 GM 阈值，去除 e[k] 直流失调
  - 收敛顺序：VCO DCC 先 → CKREF DCC → K_DTC；全部 <40µs
- **双核 VCO**：NMOS 交叉耦合 LC 薄栅；尾电感 Ls（2fosc 高阻，抑制三极管区 Q 退化）；两核完全对称、
  输出经厚栅 NMOS 开关（10Ω）耦合；第二核可断电。离散调谐 5bit 二进制+31 温度计开关电容；
  VAR_P 5bit（KVCO_P 步进 0.5 MHz/V）、VAR_I 3bit（KVCO_I 0–80 MHz/V 步进 20 MHz/V）、
  VAR_T PTAT 温补（2 MHz/°C）。LDO 0.5V 供核，PSR>55dB@10MHz。
- **倍频器**：76.8M→153.6M，PTAT 偏置复制延迟级保证占空比 <±5%（PVT）。

## 3. 我们的实现映射（12nm CLN12FFC 0.8V 核心器件）

| 论文模块 | 实现 | 状态 |
|---|---|---|
| 双核 LC VCO | 复用 base `vco_x`（NMOS 交叉耦合 + 2.49nH 电感 + moscap 变容管 + cfmom 电容组），改造为双核：两核并联 + 耦合开关 + 第二核使能 | **待改**（新） |
| DTC | 复用 `dtc_x`（RC 核 + 反相缓冲，NMOS 开关），511→**1023 码**（10-bit），Tres 390fs→**330fs**（调 R0/开关尺寸） | **待改**（新） |
| SPD | `spd_x`（PMOS 电流源充电 CR0 + 采样管 + 复位管）已与论文同构 | 复用 |
| GM+CI | `gm_x`（差分对）+ CI=2p 当前值，按论文目标 0.5µS/15pF@500kHz 复调（BW 1.2MHz → CI 更小或 GM 更大） | 复用+调参 |
| 比较器 | `cmp_x`（5 管差分 + 尾电流） | 复用 |
| 修改型 MMD+SEL | `pll_mmd_edge.va`：**已实现**双沿计数（等效 MMD 输入 ×2）+ SEL 半周期抖动 + MASH1-1 + ε 序列 | 复用+重定标 |
| DSM | 同上（MASH1-1，c1+c2−c2p） | 复用 |
| 3×sign-LMS+失调DSM | `pll_lms.va`：**已实现** kdtc/vdcc/rdcc/vref（ohat）四路 | 复用+调参 |
| 倍频器 | `pll_doubler_edge.va`（双沿 XOR 等效） | 复用 |
| DTC 码解码 | `pll_dtc_decoder.va`（温度计映射 code+255→0..510），10-bit 需扩到 **1023 端口** | **待改**（新） |
| LDO / VAR_T / PTAT | 12nm 器件 0.8V 供电无需 0.5V LDO，直接 VDD=0.8 供核；温补不做（比对窗口内温度固定） | 简化（记录差异） |

**与论文的工艺差异（记录）**：14nm FinFET vs 12nm FinFET；VCO 核供电 0.5V(LDO) vs 0.8V(直供)；
14nm 有 LDO/VAR_T 温补，我们简化。比对时 PN/抖动绝对值按比例折算（如 PN ∝ fosc³L/(Vosc²Q) 口径）。

## 4. Step 1 参数推导（76.8 MHz / 6.2 GHz，论文 Fig.16(a) 通道）

- fvco = 6200 MHz = 40.3645833… × 153.6 MHz → FCW=40.36458（论文 Fig.16(a) 标注值）
- 半周期计数口径（我们的 MMD 双沿计数）：Nint2 = 2×40.36458 = **80.72917**
  → `pll_mmd_edge Nint2=80, frac2=0.729167`；CKFB = 153.6 MHz（与 CKDTC 同率，每周期采样）
- 近整数通道：6451.3 MHz = 42×153.6M + 100k → FCW=42.000651 → Nint2=84, frac2=0.001302
- DTC：Tres=330fs，10-bit，DR=338ps；范围减半后仅用 ~50%（QE = ±1×TVCO = ±161ps @6.2G）
- SPD：斜坡周期 6.51ns（153.6M）；斜坡斜率按比较器工作区（~0.2–0.6V）设计，采样点在斜坡中段
- LMS：fref=153.6M，t_samp=6.66ns（CKFB 沿后 0.3ns）
- 近整数通道下 K_DTC 校准难度高（ε 序列慢变），论文靠 VCO DCC 保证 K 收敛
- 环路：目标 BW≈1.2 MHz；KVCO_P 主导比例增益，GM·(1/sCI) 积分

### 基准 netlist 当前参数 → 论文参数的改动清单

| 项 | base 值 | 论文值（改后） |
|---|---|---|
| fref / CKFB | 76.8M / 76.8M | 76.8M XO / **153.6M CKFB** |
| Nint2 / frac2 | 161 / 0.458333 | **80 / 0.729167** |
| DTC 位数 | 511 码 (9bit) | **1023 码 (10bit)** |
| Tres | 390 fs | **330 fs** |
| LMS fref / t_samp | 76.8M / 13.32ns | **153.6M / 6.66ns** |
| SPD 斜坡窗口 | 13.02ns | **6.51ns**（斜率/偏置重调） |
| VCO | 单核 | **双核（耦合开关+第二核使能）** |
| CI | 2p | 15p@500kHz 口径（按 BW 1.2MHz 反推重调） |

## 5. Step 2 参数推导（100 MHz / 8 GHz）

- fvco=8000 MHz / fref=100 MHz = **80 整数通道**（frac2=0，无 QE，DTC 码恒定——架构仍保持，
  校准按论文整数通道处理：mu_v=mu_k=0，仅 CKREF DCC 有效）
- Nint2 = 160, frac2 = 0
- VCO 重调至 8G：同电感 2.49nH 下 C≈159fF（6.2G 时 264fF）→ 关电容组/减固定电容；KVCO 复核
- 半周期计数率 16 GHz（VA 边沿计数无压力）；缓冲链复核 8G 能力
- SPD 斜坡周期 10ns；DTC 码恒定（整数通道）
- LMS fref=100M，t_samp=10.3ns
- 环路 BW 目标 1–2 MHz 重调

## 6. 验证计划（与论文逐项比对）

1. **VCO 开环**：PSS+pnoise，单核/双核 @100kHz/1MHz 偏移 → 比对 −98.1/−101 dBc/Hz，双核 −3dB 改进
2. **DTC**：Tres 实测（码扫），INL（DSM 真实序列激励）→ 比对 330fs / ≤1 LSB
3. **闭环锁定**：VCTRL/VREF/KDTC/VDCC/RDCC 瞬态 → 比对 <40µs 收敛、收敛顺序（VCO DCC→CKREF DCC→K）
4. **抖动**：闭环 tranNoise 或多段周期统计 + Welch PSD → 比对 83.4 fs（10k–100M 积分）
5. **杂散**：6.2G 通道 + 近整数 6451.3M 通道频谱 → 比对 <−70 dBc
6. **Step 2**：100M/8G 整数通道锁定 + 抖动
7. 全部结果入 `results/`，输出 `comparison_report.md`

## 7. 风险与预案

- **仿真成本**：6.2G 全环 40µs ≈ 本地 11min/1.5µs → 服务器预估 1.5–3h/40µs；用分段 .fc 续跑 + 先用
  tscale=1e-6 压缩校准时间窗（µs 级收敛）验证机制，再跑论文真实时间窗
- **10-bit DTC 网表规模**：1023 开关 × ~8 行 = 8000+ 行，用脚本生成
- **双核耦合启动**：两核同相锁定可能多模，按论文保持对称+开关耦合；PSS 需找振荡解
- **8G 重调**：电感固定时电容余量是否够（6.2G→8G 需 C 减 40%），不够则换电感值
- **ahdlcmi 首次编译**：服务器端每个 VA 模块逐个编译 2–10min，勿误判死亡
