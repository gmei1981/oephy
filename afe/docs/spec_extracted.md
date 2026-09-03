# 规格提取:ISSCC 2025 36.3 — UCIe-AP PHY (AFE 仿真参考)

**论文**: A 0.29pJ/b 5.27Tb/s/mm UCIe Advanced Package Link in 3nm FinFET with 2.5D CoWoS Packaging (Cadence, ISSCC 2025, paper 36.3)
**参考文件**: `20260824A_0.29pJ_b_5.27Tb_s_mm_UCIe_Advanced_Package_Link_in_3nm_FinFET_with_2.5D_CoWoS_Packaging.pdf`
**仿真目标**: VerilogA 原型仿真 + TSMC 12nm (CLN12FFCLL) 晶体管级仿真,库路径 `/home/lib/tsmc_12nm_installed` (21 服务器)

## 1. 链路总体规格

| 参数 | 论文值 | 本仿真采用 |
|---|---|---|
| 数据率 | 4 / 8 / 12 / 16 Gb/s/pin | 16 Gb/s (可切 8/4) |
| 架构 | 单端 (single-ended) 半速率 NRZ, 时钟前馈 (clock-forwarded) | 同左 |
| 半速率时钟 | 8 GHz (16Gb/s 时), 多相位来自 PLL (100MHz 参考) | 8 GHz, 相位可编程 (PI) |
| 通道 | 2.5D CoWoS-S, ~1.4 mm, 45μm micro-bump pitch | 1.4 mm 无源通道模型 |
| 供电 | VDD=0.75V, VDDH=1.2V, VCCIO=0.45V (低摆幅模式) | VDD=0.8V(12FFC 核心额定), VCCIO=0.45V |
| 单模块 | 64 TX + 64 RX 数据 lane, 297mW, 0.29pJ/b | 单 lane AFE 仿真 |
| 延迟 | FDI-to-FDI 3.5ns | — |
| 密度 | 5.27Tb/s/mm edge bandwidth | — |

## 2. RX AFE 架构 (Fig. 36.3.3.b — 本仿真的核心)

- **未端接 AFE** (unterminated):RX 输入端高阻,直接接比较器输入(短距 D2D 链路省端接功耗)。
- **Ping-pong 自校零比较器 (autozero comparator)**:
  - 两个完全相同的比较器 bank,输入数据由 ping-pong 开关在二者之间周期性切换;
  - 一个 bank 评估 (evaluation) 时,另一个 bank 预充电/自校零 (precharge/autozero);
  - 定期刷新 (regular refresh) 实现周期性漂移消除 (periodic drift cancellation),保证比较器输入低失调;
  - ping-pong 控制逻辑由慢时钟 **PCLK ≈ 100MHz** 驱动,产生预充电/评估时序;
  - 预充电脉冲宽度被压缩到最小以降低功耗。
- **Vref 由 8b DAC 产生**,链路训练期间校准,用于消除数据通路 DCD;Vref DAC 量程 **450mV**(低摆幅模式)。
- **半速率采样**:odd / even 两路采样器,各以 8GHz 采样;后接 2:8 解串器。
- 时钟:单相位 8GHz 分布到所有数据 lane;每 lane 可编程 deskew(训练时校准,补偿数据/时钟通路延迟差)。

## 3. TX 架构 (Fig. 36.3.2)

- 每 TX lane:8:1 串行器 (8:2 SER + 2:1 MUX) → 可编程预驱动 → 驱动级。
- 预驱动将电平从核心 VDD 平移到驱动电源 VCCIO。
- 驱动级:**P+N over N CMOS 架构**,支持高摆幅/低摆幅两种模式(由 VCCIO 值决定);专用驱动电源使输出级工作于低于核心电源的电压(低功耗配置)。
- PLL(环振型)由 100MHz 参考产生 8GHz 多相位时钟;CPI(时钟路径)/DPI(数据路径)相位内插器完成时钟定位。

## 4. 实测性能 (仿真对照目标)

| 指标 | 16Gb/s | 12Gb/s |
|---|---|---|
| 眼宽 (EW) | 0.56 UI @ BER 1e-9 | 0.69 UI |
| 眼高 (EH) | 220 mV | 360 mV |
| BER 1e-15 眼宽 | 0.325 UI (2 link) / 0.29 UI (8 link) | — |
| 浴盆 @ 1e-27 | 0.07 UI | >0.17 UI |
| 测试码型 | PRBS23, 无 FEC/CRC | 同左 |

## 5. 12nm PDK 适配 (3nm → 12FFC)

- TSMC CLN12FFCLL (`cln12ffcll_1d8_sp_v1d0_2p4`),核心器件额定 **0.8V**(12FFC 标称),故 VDD 取 0.8V(论文 0.75V 的直接等效)。
- 器件:`npode_svt_mac` / `ppode_svt_mac`(3 端 wrapper,参数 `l`、`nfin`;另有 hvt/lvt/ulvt/lnvt 可选),`nch_svt_mac`/`pch_svt_mac`(4 端)。
- 模型 corner 段:`top_tt` / `top_ss` / `top_ff` / `top_sf` / `top_fs`。
- VCCIO=0.45V 低于核心额定 0.8V,输出级与采样器可用核心器件;1.2V 域(如需)用 IO 器件或堆叠。
- 仿真器:Spectre 25.1 (`/edatool/cadence/spectre2510.10.393/bin/spectre`),许可 Virtuoso_Spectre @ 192.168.110.18:5280。

## 6. 仿真验证目标

1. **VerilogA 原型 (行为级)**:TX(PRBS23@16G)→ 驱动 → 1.4mm 通道 → ping-pong 自校零比较器 RX AFE → odd/even 采样 → 2:8 解串 → PRBS 校验。
   - 链路 BER ≤ 1e-9(仿真时长内);眼图(扫 Vref DAC 码 × 采样相位)验证 EW/EH;自校零对失调的抑制(注入失调 → 校零后残留)。
2. **晶体管级 (12nm)**:自校零 StrongARM 比较器 bank + P+N-over-N TX 驱动级用真实 PDK 器件;其余(通道、时钟、串行器)沿用行为级。
   - 比较器 16Gb/s 判决正确性、失调校零有效性(注入失调后 BER 恢复)、驱动级摆幅/阻抗/功耗、与原型对比。
