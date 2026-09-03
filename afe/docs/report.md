# UCIe-AP RX AFE 仿真报告 — VerilogA 原型 + TSMC 12nm 晶体管级

**参考论文**: ISSCC 2025 36.3 — A 0.29pJ/b 5.27Tb/s/mm UCIe Advanced Package Link in 3nm FinFET (Cadence)
**仿真环境**: Spectre 25.1 @ 192.168.110.21,PDK = TSMC CLN12FFCLL (`/home/lib/tsmc_12nm_installed`,section `top_tt`)
**日期**: 2026-08-24(初版)/ 2026-09-03(流片准备版:P0-P6 补电路 + 验证闭环)

## 1. 仿真内容

| 仿真 | 内容 | 结果 |
|---|---|---|
| VerilogA 原型链路 | TX(PRBS23@16G)→驱动→1.4mm 通道→ping-pong 自校零比较器 AFE→半速率采样→真 BER 检测 | **BER = 0**(959 bits) |
| VerilogA 眼图扫描 | Vref DAC 码 × 采样相位 (117 点) | 零误码区 **74–413 mV**(眼高 339 mV) |
| VerilogA AZ 演示 | 注入 200 mV 失调,AZ 开/关/静态校准对比 | AZ 开 0.3% / 关 15.5% / 静态校准 23.1% |
| 12nm 晶体管链路 | 晶体管 TX 驱动 + ping-pong 自校零差分对 AFE + 晶体管 mux | **BER = 0**(1279 bits) |
| 12nm 眼图扫描 | 76 点 | 零误码区 **229–371 mV**(眼高 ≥142 mV)、宽度 ≥0.94 UI |
| 12nm AZ 漂移演示 | 恒流注入 gp 节点模拟慢漂移(4.5 mV/ns) | **AZ 开 0 / 关 10.5%** |
| 补电路链路(P0-P4) | 二级 AZ 比较器 + 2×16-fin 复制偏置(0.362 V)+ 8b R-2R DAC + ESD(nf=100)+ 封装模型(RS/LS) | **BER = 0**(639 bits) |
| 眼图终版(P6) | 13 vref × 8 相位(104 点) | 零误码 **90–200 码 = 159–353 mV**(眼高 194 mV) |
| Corner × 温度(P5) | 7 配置 × 2 相位 × 13 vref(温度经 `options temp=` 真正生效) | **7/7 零误码**;最差 ss 90–140 码(眼高 88 mV) |
| 失调 MC(P5) | 200 seeds 逐 seed 枚举(az_on) | **mean −2.5 mV,σ = 23.6 mV**(6σ = 142 mV < 眼窗 194 mV) |
| TX Ron MC(P5) | 200 seeds(2 mA 强制,本地重解析) | Ron_pu 249.9±0.2 Ω / Ron_pd 244.1±0.2 Ω(σ = 0.1%) |
| 噪声(P5) | 器件噪声 on/off 冒烟 + 链路 3 点(40 ns) | on std 3.8 mV;off/on_1/on_2 链路 **全 BER = 0** |
| 电源(P5) | VDD 正弦注入 0–100 mV @100/400 MHz + 键合线 LS 0.1/1 nH | 10/10 **BER = 0**;LS=1nH vss_pk = 398 mV 仍零误码 |

图:见 `output/va_eye.png`、`va_wave.png`、`tran_eye.png`、`tran_wave.png`、`az_compare.png`、
`tran_corners.png`、`tran_mc_offset.png`、`tran_mc_ron.png`、`tran_supply.png`、`dac_linearity.png`。

## 2. 架构实现要点(对照论文 Fig. 36.3.3)

- **未端接 AFE**:RX 输入高阻,直接电容耦合到比较器输入(耦合电容 50 fF,模拟 MOM cap)。
- **Ping-pong 自校零**:两个比较器 bank 由 PCLK(100 MHz)交替;每个 bank 在其离窗期的前 1.5 ns 执行 AZ(输入板→VREF、栅极→VBIAS=0.4 V、输出短路),论文所称"最小化预充电脉冲"。
- **Vref 8b DAC**:450 mV 满量程,与论文一致;训练校准(仿真中通过 Vref 扫描体现)。
- **半速率采样**:odd/even 采样器在 8 GHz 时钟上升/下降沿交替判决。
- **TX 驱动**:P+N over N 结构,专用 VCCIO=0.45 V;12nm 实现 256 fins ulvt PMOS 上拉 + 96 fins ulvt NMOS 下拉(≈28 Ω,与线匹配),VDD 域三级预驱动。
- **真 BER 检测**:TX 复制 LFSR + 移位对齐的自检 checker(自同步 checker 无法检出死链路,见 §4)。

## 3. 晶体管级设计要点(12nm 适配)

| 模块 | 实现 |
|---|---|
| 比较器 bank (`tran/afecmp_bank.scs`) | **二级**:一级 lvt 差分对(nfin=8)→ 二级 ulvt 对(一级输出接二级门极,线性增益再生);AZ 开关 ulvt nfin=8,caz=80 f;ping-pong 交替,离窗期重锚定——消**漂移**不消静态失配(由 vref 训练吸收,论文机制一致) |
| 复制偏置 (`tran/afe_bias.scs`) | 2×16 fins lvt 二极管 + rhim 2.35 µ + 16×cfmom 去耦;DC 平衡点 **0.362 V**。要点:8 fins 自然平衡 0.455–0.48 V 会毁眼图——复制器件要**加宽**以压低锚定点 |
| Vref DAC (`tran/afe_dac_r2r.scs`) | 8b R-2R,6 kΩ 单元,TG 臂 2×16 fins,MSB 臂 −0.9% 微调;实测 **DNL 1.0 / INL 1.85 LSB**(近单调,code 127 处 −0.64 LSB) |
| ESD (`tran/afe_esd.scs`) | 双二极管,nf=100(≈300 fF/焊盘)零误码;nf=960 崩溃(拐点 100–960) |
| 驱动 (`tran/afe_tx_drv.scs`) | 3 级 svt 预驱动(VDD=0.8 V)+ ulvt 输出级(256/96 fins)直驱(电平移位器不必要,VCCIO<VDD,Vgs 在额定内) |
| Mux | NMOS+PMOS 传输门(每个 4 fins),bank 选择 = a_eval/b_eval |
| 通道 | 理想 tline(z0=30 Ω 匹配驱动阻抗,td=9 ps,1.4 mm)+ RX 焊盘电容 50 fF + 串扰注入 |

**器件库要点**(实测确认):
- `npode/ppode_*_mac` 3 端 wrapper **源漏短接**,不能当开关管用;开关/放大器须用 4 端 `nch/pch_*_mac`。
- 各 flavor 在无 flag 下均正常导通(svt/lvt/ulvt/hvt);`lnvt` 的 l=16n 违反 RDR。
- VCCIO=0.45 V 域 PMOS 电流密度低(ulvt ≈ 14 µA/fin @ Vsd=0.1)→ 28 Ω 上拉需要 ~256 fins,这是 12nm 低摆幅 TX 的现实代价。

## 4. 关键发现与调试记录

1. **自同步 PRBS checker 掩盖死链路**:链路全 0/全 1 时自同步 checker 预测自洽、误报 0 误码。改用 TX 复制 LFSR 真 BER 检测后发现:早期"BER=0"的 VA 原型实际是死链路(VA laplace_nd 滤波器输出为 0,主通路断开)。
2. **VA 原型死链路根因**:`laplace_nd` 在行为级 TB 中输出为 0 → 改用纯延迟+衰减通道模型后链路恢复。
3. **TX 驱动极性反转**:去掉电平移位器时输出级少一级反相 → 3 级预驱动修复。
4. **npode wrapper 的源漏短接**导致驱动级虚接(二极管式连接),换 4 端器件后摆幅恢复。
5. **VCCIO=0.45 V 域 Ron 量级**:实测 ulvt 电流密度决定输出级需要 250+ fins 才能达到 28 Ω。
6. **漂移演示要点**:漂移须注入高阻电容节点(gp)才体现 AZ 的价值——低阻输出节点上的电流源产生瞬时失调,短路复位无效。
7. **binned 模型 nfin 上限 ~20.9**:大器件须并联分段。

## 5. 结果对比(论文 vs 本仿真)

| 指标 | 论文(3nm) | VA 原型 | 12nm 晶体管 |
|---|---|---|---|
| 数据率 | 16 Gb/s | 16 Gb/s ✓ | 16 Gb/s ✓ |
| BER(仿真时长) | 1e-9@扫瞄 | 0(959 bits) | **0(639 bits,含 ESD+真实偏置+封装)** |
| 眼高 @ BER≤1e-3 | 220 mV(1e-9) | 339 mV | **194 mV**(全链路;最差角 ss 88 mV) |
| 眼宽 | 0.56 UI(1e-9) | ~1 UI | ≥0.94 UI |
| 失调消除 | ping-pong AZ | ✓ 200 mV 失调→0.3% | ✓ 4.5 mV/ns 漂移→0;静态失调 MC **σ=23.6 mV**(vref 训练覆盖 6σ=142 mV) |
| 功耗 | 297 mW/模块 | — | 比较器 ~2×20 µW + 驱动 289 µW/lane |

**Corner × 温度(7 配置,P5)**:tt@25 90–200 码(194 mV)/ ff@25 90–210(212)/ **ss@25 90–140(88 mV,最差,160+ 码 BER≈13%)** / sf@25 90–210(212)/ fs@25 90–190(176)/ tt@−40 90–190(176)/ tt@125 90–210(212)。所有配置低边一致在 90 码,角效应只收缩高边;ss 慢角是流片裕度瓶颈,fs/tt−40 眼高 176 mV 临界(180 mV 目标)。

**温度机制注记**:Spectre 分析级 `temp=`(dc/tran 行)对本 PDK 的 TMI binned 模型**静默无效**,必须用命名 `options` 语句(`simOpts options temp=`);实证 −40/25/125 °C 偏置平衡点 0.385/0.363/0.330 V。此前所有标 TEMP=25 的仿真实际在 27 °C(差异可忽略,但温度角在修复前从未真正跑过)。

## 6. 文件清单

```
afe/
├── docs/spec_extracted.md   论文规格提取
├── docs/report.md           本报告
├── status.md                跨会话状态(环境/参数/踩坑记录)
├── va/                      VerilogA 模型(11 个模块)
├── tran/                    12nm 电路:二级 AZ 比较器 / 复制偏置 / R-2R DAC / ESD / TX 驱动 / SA 采样器(备用)
├── netlists/                TB 模板(链路/眼图/DAC/MC 失调/MC Ron/偏置探针/噪声)
├── scripts/                 run/plot 脚本(virtuoso-bridge → 21 服务器;含 probe_bias/reparse_mc_ron)
└── output/                  全部结果 JSON + PNG
```

## 7. 后续工作建议

- **ss 慢角眼高(88 mV)是流片裕度瓶颈**:针对慢角高 vref 侧优化——0.387 V 锚定下的比较器余量/二级增益分配(fs/tt−40 的 176 mV 也低于 180 mV 目标);
- 双 bank 独立失调差(σ≈35 mV)的训练策略——训练最大风险项(单 bank 失调 σ=23.6 mV 已由 vref 训练覆盖);
- 真实 StrongARM 采样器:每比特复位、独立时钟纪律、输入建立与失调校准(`tran/afe_sampler.scs` 链路已实测系统失调并记录,AC 耦合/vcm/ts 复位均未解决,需独立设计);
- PDN 振荡阻尼方案:LS=1 nH 实测 vss_pk=398 mV 且 BER=0,但裕度依赖去耦相位,数据恒定时持续振荡(~150 ps 周期);
- 用 PDK MOM cap(`cfmom_2t`)替换比较器理想耦合电容(偏置去耦已用 cfmom);
- 多 lane 串扰/电源噪声场景(论文 8 链路互扰浴盆曲线;单 lane 电源注入已验证 BER=0);
- 12/8/4 Gb/s 多速率配置验证;
- 完整 ping-pong 数字控制 + 训练状态机(可复用 `smic_test/ucie_isscc` 中的 VA 模块);
- 版图/DRC/LVS(本期范围外)。
