# alg0914 — ADPLL 顶层闭环算法仿真交付（快照）

日期：2026-09-14 快照（继承 alg0908 全部历史：2026-09-08 建立；2026-09-11 更新（DTC 按 spec 建模 + fbank 暂时改为 1bit/1阶SDM + DCO PN 改 −120dBc/Hz@1MHz/10dB/dec + 输出相噪分解 noise_budget）；2026-09-13 更新（noise_budget 增至 14 run：补 REF 抖动 / TDC 热噪声 / glitch 扫参，见下节）；2026-09-14 更新（noise_budget 增至 25 run：**glitch 在真实 3bit fbank（dsm_dco_mode=2）下重评 + budget_m2 全 mode2 实测自洽**；同日第二轮：**DCO PN 换真实分段 spec（100k/−76, 1M/−105, 10M/−129, 100M/−151）+ 锁定环路 250k→4.84MHz（kp1 1.664→512, ki1 0.416→4, PM 2.7°→62.4°）重跑全部预算**，见"真实 spec + 5MHz 环路"节））
来源：`alg0908/` 2026-09-14 第二轮完成态（其原始开发位置 `algorithm/ADPLL/TOP/`），本目录为自包含快照，可在本目录内直接运行；输出仅含指标/日志/曲线，IND/DBG 向量重跑即生成。

## 内容

```
alg0908/
├── README.md            本说明
├── TOP/                 顶层闭环仿真
│   ├── top_adpll.m      主循环（FSM: FLL→PLL→LOCK + 9个黄金模块 + 行为级被控对象）
│   ├── check_units.m    14项单元检查（TDC往返/DSM实例等价/分频器恒等式/物理FLL/DCO增益/AFC选带/PN频谱验证/INL查表/DTC INL-DNL表/DTC PN换算等）
│   ├── cfg/             3个场景配置（top_cfg.txt / top_cfg_dtc_off.txt / top_cfg_no_calib.txt）
│   ├── funcs_top/       DSM实例安全变体 + TDC/分频器/DCO/FLL计数器行为级模型 + FSM/PSD/指标/绘图
│   └── output/<场景>/   运行结果：5张PNG + metrics.txt + 25个IND + 26个DBG向量 + README.txt + run.log
└── funcs/               黄金定点算法模型（TOP 通过 ../funcs 引用，未做任何修改）
```

## 运行方法

```bash
cd alg0908
matlab -batch "addpath('TOP'); run('TOP/check_units.m')"   # 单元检查（~1分钟，应 ALL PASS）
matlab -batch "addpath('TOP'); top_adpll"                   # 默认场景（全校准，~3-8分钟）
matlab -batch "addpath('TOP'); top_adpll('dtc_off')"        # DTC关闭对照（演示相位无法锁定）
matlab -batch "addpath('TOP'); top_adpll('no_calib')"       # 校准全关对照（kdtc固定300）
matlab -batch "addpath('TOP'); noise_budget"                # 噪声分解：25个run（mode0 14 + mode2 重评 11；新run才闭环，已缓存的读盘）
                                                            # -> output/noise_budget/ 三张曲线+txt
```

条件：**fref = 100 MHz**，FCW=80.25（8.025 GHz，frac=0.25），262144拍=2.62ms。
DCO：VCO 标称 8GHz；pbank 6bit 覆盖 7.67~8.90GHz（64子带×30MHz带宽，间距 19.047619MHz）；abank 9bit=511子带覆盖30MHz（LSB 58.7kHz）；**fbank 双架构并存**（`dsm_dco_mode`）：mode0=1bit（单单元=1个abank LSB，lpf_frac 直接进 1阶SDM {0,1}，占空比平均——单单元必须跨满 1 LSB 才能覆盖 [0,1) 分数）；mode2=3bit（8单元温度计码×1/8 LSB，DSM 输入 mod(8f,1)+静态 floor(8f)）。clk_dsm=DCO÷4（≈2.006GHz，即每参考周期 FCW/4≈20.06 子步，cfg `dsm_dco_oversample: 20`）。
DTC 按 spec 建模：**PN floor ≤−160 dBc/Hz @fout=100MHz（换算 159fs 白边沿抖动）+ INL 2LSB（平滑随机，相关长度64码）+ DNL 1LSB（非累积单元失配）**；合成二次项 `dtc_inl2_a` 归 0。
100MHz 联动换算（保持时间域动态不变）：afc_ref_cnt_thr 7→9（窗口时间不变、计数分辨率 1.5625MHz/count）、freq_lock_thr 6→3（count LSB 变 781kHz）、kp2 48→64（每拍环路增益÷4 补偿）；kp1/ki/kdtc/DTC/TDC 以 Hz 为单位自动不变。DCO 相噪模型：**L(f)=max(−150, −120+10·log10(1MHz/f)) dBc/Hz**（1/f 区域，`dco_pn_slope_dbdec` 可调斜率，原 30dB/dec=1/f³ 路径保留默认）。

## 结果摘要（100MHz 参考clk，真实非理想模型，见 TOP/output/<场景>/）

本轮（2026-09-11 下午）修改：**DCO 相噪改为 −120dBc/Hz@1MHz、10dB/dec（1/f）、floor −150**（`dco_pn_slope_dbdec` 可调斜率）；新增 **输出相噪分解 `noise_budget.m`**（曲线见 `output/noise_budget/`，下节）。

| 指标 | default | no_calib | dtc_off | fb3 | 规格 |
|---|---|---|---|---|---|
| 相位锁定 | **150.4µs ✓** | 150.9µs | 不锁定（DTC必需） | 150.4µs | **≤200µs 达标** |
| 频率误差 | 4.1 kHz (0.51ppm) | 5.2 kHz | 5.0 kHz | 5.2 kHz | 1ppm |
| kdtc | 300→269.3（−3.5%） | 固定300 | — | 269.3（−3.5%） | — |
| 25MHz 分数杂散（鉴相器域） | **−34.9 dBc** | −21.2 dBc | — | −34.9 dBc | 校准收益 13.7dB |
| 50MHz 二次谐波 | −44.1 dBc | −27.0 dBc | — | −44.0 dBc | — |
| phe RMS（鉴相器域） | 1352 fs | 3.58 ps | — | 1353 fs | 200fs（见下节） |
| **输出 σt（12.2k..50M积分）** | **1423 fs** | — | — | — | 200fs |

（2026-09-14 第二轮起：DCO PN 为真实分段 spec、锁定环路 4.84MHz/PM62.4°——频差从 ~0ppm 升至 0.51ppm 是真实 1/f³ 低频游走+估计窗所致，仍达标；phe/σt 变化见"真实 spec + 5MHz 环路"节。上一轮假设 spec+250kHz 环路的旧表：锁定 147.4µs、频差 127Hz、杂散 −34.7/−46.5、phe 915fs、σt 1178fs）

上一轮（−108dBc/Hz@1MHz、30dB/dec 时）：锁定 150.4µs、phe 4.88ps、频差 8.8kHz（1/f³ 游走）——换成 1/f 剖面后 phe 降 5.3×、频差降 69×、锁定加快 3µs、杂散不变（杂散由 DTC INL 决定，与 DCO PN 无关）。

## 输出相噪分解（noise_budget，`TOP/output/noise_budget/fig_nb2_pn_decomp.png`）

逐源单独闭环（其余理想化：`tdc_ideal`/`dsm_fb_ideal`/噪声 cfg 关断），输出相位误差 e(i)=phi_abs−i·FCW 锁定段（1.65ms 后，校准全收敛）Hann-Welch PSD（RBW 12.2kHz），σt 积分 12.2kHz..50MHz：

| 噪声源 | σt (fs) | L@200kHz | 说明 |
|---|---|---|---|
| **细bank切换 glitch（100fs/code）** | **1107** | −92 dBc/Hz | **最大分量但轨道依赖**（见下"glitch 扫参"）；自激轨道上 abank 在 206/207 边界往返（78%/21%），每次翻转 = 8 单位码踢 800fs |
| **TDC INL（1LSB 平滑随机）** | **883** | −107 dBc/Hz | 第二大；DSM 锯齿扫过 INL 曲线的失真写入输出 |
| DCO PN（−120/10dB/dec） | 325 | −106 dBc/Hz | 1MHz 以上≈自由运行（−117@1M 实测 vs −120 标称），带内抑制 |
| **TDC 热噪声（0.1 LSB≈49fs，假设值）** | **107** | −117 dBc/Hz | 2026-09-13 新增；tdcnq−tdcq 功率差；探测器白噪声带内直通——**比 DTC 热噪声还大，值得向模拟端要一个真实 spec** |
| DTC 热噪声（159fs 白抖动） | 79 | −112 dBc/Hz | 带内（~200kHz）透传带外抑制 |
| DSM 量化泄漏（经 DTC INL/DNL） | 55 | — | dsmq−tdcq 功率差；输出域杂散仅 −129dBc@25M（分数杂散主要在鉴相器域） |
| TDC 量化（1/256 周期，抖动下） | 12 | — | **远小于鉴相器域的 141fs**——输出只积分环路带宽内部分 |
| REF 抖动（50fs RMS，假设值） | 24 | −121 dBc/Hz | 2026-09-13 新增；spec 无此指标，50fs 假设下带内直通仅 24fs（若 REF 为 200fs 则 ≈96fs，仍非主宰） |
| **RSS(分量)** | **1457** | | vs total 1178fs：超 24%——glitch×TDC INL 非线性交互（两强项部分重叠） |

**glitch 扫参（fig_nb3 实线，mode=0）：σt(10/30/100/300 fs/code) = 1/1/1107/1 fs——不是平滑的线性标度。**机理：1bit fbank 锁定后 SDM 输入恒定 → 32 子步模式逐拍完全重复 → code8 稳定 → dstep=0 无踢（安静轨道，任何幅度都 ≈0）；100fs run 在锁定过程中被自身踢进入 **abank 整数边界自激极限环**（lpf_out 在 207 边界附近双峰 206.6/207.0，翻转即 8 单位码踢）而自持。即"glitch=1107fs"是**最坏轨道**而非期望值。（→ 2026-09-14 已在 mode=2 下重评，见下节）

## mode=2 真实 3bit fbank 重评（2026-09-14，noise_budget 增至 25 run，fig_nb3 虚线）

`dsm_dco_mode=2`（8 单元温度计码，单位码=1/8 abank LSB，DSM 输入 mod(8f,1)+静态 floor(8f)）下重测 glitch 与全部鉴相器域项（`budget_m2` 全部 mode2 实测，仅 DCO/DTC 为 plant/边沿属性跨模式复用）：

| 项 | mode0 (1bit) | **mode2 (3bit, 真实架构)** |
|---|---|---|
| glitch @100fs/code | 1107（最坏轨道） | **795 fs**（seed 7/1/2/3：795/822/819/737，±5% 稳定） |
| glitch 扫参 10/30/100/300 | 1/1/1107/1 | **0/0/795/2543**（30~100 间阈值；阈值以上近线性 σt≈8×fs/code） |
| TDC INL | 883 | **873**（dsmq/tdcq/tdcinlq 全部 mode2 重测） |
| DSM 泄漏 / TDC 量化 | 55 / 12 | 53 / 12 |
| **total σt** | **1178 fs** | **877 fs（−25%）**；锁定 147.4µs ✓、phe 863fs、kdtc 270 不变 |

**机理（DBG 实证）**：mode2 的 glitch 仍是**码边界自激抖振**，与 mode0 同族但单位踢从 800fs 降到 100fs——100fs/code 锁定段 abank 206↔207 翻 296 次、dsm_code 0-7 乱跳 5510 次（kick→phe→lpf_frac 反馈自持）；10fs/code 时 dsm_code 冻死在 7、零切换（安静轨道，PSD 到数值底）。**"1bit 伪影"只解释 1107→795 的降幅，消不掉 glitch**。注意 10/30fs 的"0"是 solo-run 安静轨道假象：真实系统噪声常开（total_m2 中 dsm_code 切 8815 次），抖振区标度 σt≈8×(fs/code) → **glitch 贡献 ≤100fs 需切换 glitch ≤ ~12fs/单位码（给模拟端的 spec）**。

**次可加发现**：total_m2(877) ≈ tdcinlq_m2 solo(875)，远低于 RSS(1229，−29%)——TDC INL 与 glitch 两强项共骑同一环路状态、部分相消，线性叠加假设在双强源下失效；单源 solo 值只可作排序/上界用。

## 真实 DCO spec + 5MHz 环路重评（2026-09-14 第二轮，全 25 run 重跑）

**改动**：①DCO PN 换**实测分段 spec**（100k/−76, 1M/−105, 10M/−129, 100M/−151 dBc/Hz；29/24/22 dB/dec 多拐点）——`pn_gen_1f3` 加分段插值模式（cfg `dco_pn_spec_f_hz/dbc` 逗号表，log-log 插值+端斜率外推；check_units 第10项 5 频点 ±1.7dB 验证）；②锁定环路 kp1 1.664→512、ki1 0.416→4 → **fc=4.84MHz、PM=62.4°、峰化 1.5×**（原锁定环路 PM 仅 **2.7°**、误差峰化 **21×**@248kHz——之前所有噪声堆角上的根源；捕获态 kp2=64 不变，交越 614kHz）。

| 项 (σt, mode2) | 旧（假设spec+250k, PM2.7°） | **新（真实spec+4.84M, PM62°）** |
|---|---|---|
| DCO | 325 | **128 ↓**（带内 34dB 更差的 PN 被宽环路压掉；10M 以上实测本就干净） |
| TDC INL (1LSB) | 873 | **≈0**（tdcinlq 189.8 vs dsmq 206.5——加 INL 反而略降） |
| TDC 量化 | 12 | **150**（白噪声≈全通过 Nyquist） |
| DSM 泄漏 | 53 | 143 |
| DTC 热 / REF 抖动 | 79.6 / 24 | 79.6 / 25（不变） |
| **glitch** @100fs/code | 795（seed ±5% 稳定） | **1394，seed 双峰 1394/0.4/0.4/1035（50% 捕获轮盘回归）** |
| **total** | 877 | **1421**；锁定 150.4µs ✓、频差 4.1kHz(0.51ppm)、phe 1352fs、kdtc 269、输出 25M 杂散 −90（DSM 泄漏进输出域） |

**结论修正**：
1. **旧"TDC INL 873fs 需 ≤0.2LSB"结论作废**——873fs 主要是 PM=2.7° 的 21× 角谐振伪影，阻尼修好后 1LSB INL 的输出贡献 ≈0。环路阻尼（PM）比 INL 幅度更关键；
2. **真实 DCO spec 在 5MHz 环路下完全可接受**（128fs，比旧假设还好）；
3. **代价一：glitch 抖振恶化**——kp1=512 使 100fs 踢的环路响应 = 0.41 abank LSB = 3.3 单位码，捕获变 50% 轮盘，chatter 标度 8×→**14×fs/code**（1394/100、4486/300）→ glitch≤100fs 需 **≤~7fs/code**（更难）；环路增益×踢 = chatter 放大器，**带宽与 glitch 正相杀**；
4. **代价二：TDC 白噪声成硬底线**——量化 141fs ≈全通（150fs = 200fs 预算的 75%），TDC 热噪声 spec 重要性 ×3；带宽↑ → 白检测噪声通过↑；
5. 权衡本质：DCO 抑制要带宽、glitch/TDC 白噪要低带宽+低 kp。**5MHz 过宽**——DCO 实测 10M 以上本就 −129dBc/Hz，~1–2MHz 阻尼环路即可兼顾（待扫参验证）。

关键结论（2026-09-14 第二轮后为准，旧结论见"mode=2 真实 3bit fbank 重评"节）：
1. **环路阻尼比噪声源幅度更关键**：原锁定环路 PM=2.7°/峰化21×，把 TDC INL 的带内相关误差放大成 873fs 角谐振；PM 修到 62° 后 1LSB INL 输出贡献 ≈0（旧"INL≤0.2LSB"要求作废）；
2. **真实 DCO spec（100k/−76 起）在 4.84MHz 环路下 128fs，不是瓶颈**；DCO 抑制要带宽、glitch/白噪要低带宽——**带宽是最核心的权衡旋钮**（glitch chatter 标度随 kp 从 8×升到 14×fs/code，且 seed 捕获重新轮盘化；TDC 白噪声 141fs 全通 = 预算的 75%）；
3. 当前 5MHz 配置 total=1421fs，主宰是 glitch 抖振（1394fs@100fs/code，50% seed 捕获）——~~建议扫 1–2MHz 中间带宽找最优点~~（**已验证推翻**：2M/3M total 更差 1561–1796fs，见"带宽扫参闭环验证"节）；
4. （沿用）输出域≠鉴相器域；分数杂散 −34.9dBc 在鉴相器域，kdtc 收敛 269.3（−3.5%）为随机 INL 最优线性拟合；鉴相器域杂散要 −50dBc 需逐码 INL 查表。

诊断运行（不在预算内）：`tdc`（eq≡0 相位静止）→量化噪声退化为 0；`dsm`（理想TDC无抖动）→kdtc/g2 相关器确定性极限环 606fs 伪影（真实抖动下 kdtc 收敛 279.4、泄漏仅 ~55fs）。

## 带宽扫参闭环验证 + jitter 根因定位（2026-09-14 第三轮，`bw_sweep_probe.m`/`nb_bw_verify.m`/`nb_ng*.m`）

上节"建议扫 1–2MHz 中间带宽找最优点"的假设**已被闭环实测推翻**。新增 total 运行（全源、mode=2、锁定段 σt，seed 括注）：

| fc | total（fs） | **无 glitch 底噪**（fs） | glitch 贡献（fs） | 标度系数 |
|---|---|---|---|---|
| 2.0 MHz（kp1=213.7/PM78°） | 1676/1656/1796（s7/s1/s3） | **282** | ~1652@100fs/code | **16.3×fs/code**（10/30/100fs 实测 164/483/1652，严格线性） |
| 3.0 MHz（kp1=320.3/PM73°） | 1561/1637（s7/s3） | **231** | ~1544@100 | ~15.4× |
| 4.84 MHz（现配置） | 1421（s7） | **227** | ~1403@100（10fs→135） | **14×** |
| glitch solo@2M | — | — | **0.3**（安静轨道，0 次切换） | — |

**根因（DBG 实证）**：jitter 98.5% 的功率来自 fbank 切换 glitch 的**再生式抖振**，且是**环境噪声驱动**而非自激——glitch solo 在 2MHz 完全安静（0 切换），但全源下 TDC 量化噪声（141fs）经 kp=512 放大成 lpf_frac ±0.29 LSB 摆动（Q26 实测 std≈0.29）→ 锁定段 8 万次/ms 码切换（|dstep|≈3）→ 每次切换给 DCO 相位**永久**加 100fs·dstep·randn 台阶 → 单次 kick 经 kp 再生 >1 LSB 指令摆动 → 自持极限环。线性小信号模型只预测 ~26fs（差 50×），证实是再生机理而非传递函数问题。带宽降低**不解决问题**：切率∝kp、压制∝1/√fc，两者近似抵消，实测标度系数 16.3×(2M)→14×(4.84M) 仅缓变，而线性底噪在低带宽端反而抬升（DCO 抑制不足）。

**结论**：
1. **模拟端 spec 是唯一主杠杆**：glitch 贡献 ≈ (14~16)×(fs/code)，要 glitch ≤100fs 需 **fbank 切换 glitch ≤ ~7fs/单位码**（全带宽范围近似不变，无须靠带宽换）；
2. **需向模拟端核实 glitch 物理形态**：当前模型是"永久相位台阶"（最坏情况）。若实测为衰减振铃（ns 级 settle、净相移≈0），贡献会塌缩到远小于上表——这是最高杠杆的待验证建模假设；
3. **即使 glitch=0 也到不了 200fs**：无 glitch 底噪 227fs@4.84M（=TDCq149+DSM泄漏143+DCO128+DTC80+REF25 次可加），**spec 200fs 需底噪再降 ~25%**——按序：DSM 泄漏（DTC 逐码 INL 查表）、TDC 分辨率/热噪 spec（热噪目前 0.1LSB 假设值，若实际 0.3LSB 将再加 ~150fs@5M，必须落实）；
4. **维持 fc≈3–5MHz**（底噪 227–231 平坦最优），不要降带宽；
5. 数字侧可探索（本轮未验证）：lpf_frac 进 fbank DSM 前加迟滞/死区切断再生环；用 DTC 预失真补偿 kick 的确定性分量（数字已知 dstep；注意模型 randn=零均值最坏情形，实际确定性分量可标定可补偿）。

运行入口：`matlab -batch "addpath('TOP'); bw_sweep_probe"`（解析扫参）、`nb_bw_verify`/`nb_ng`/`nb_ng_b`（闭环验证，结果缓存于 `output/nb_tot{2,3,5}m_*`，汇总 `output/noise_budget/bw_verify.txt`）。

## 实测 glitch 律下的噪声预算重跑（2026-09-14 第五轮，`nb_gmeas*.m`）

**输入**：fbank glitch 已在 12nm 晶体管级实测（adpll_ted/sim/GLITCH_MEAS.md）：**每切换一次的相位台阶 = 91±1 fs × 单元设计步进(MHz)**，台阶型、on/off 抵消 98.5%。换算到本模型：mode2 单元(7.34kHz)→**0.67fs/code**；mode0 单元(58.7kHz)→**5.34fs/code**（原假设 100）。当前框架（真实 spec、4.84M、K=20）重跑：

| 项 (fs) | **mode2 (0.67fs/code)** | **mode0 (5.34fs/code)** |
|---|---|---|
| glitch solo | **0.6**（自激阈值以下，抖振死亡） | **6.8** |
| glitch 贡献（total−底噪） | ~10 ≈ 14×0.67 ✓ 标度律成立 | ~74 ≈ 16.3×5.34 ✓ |
| **total (seed7)** | **226.8**（=底噪 227） | **237.7** |
| total (seed1) | **342.8** | **350.2** |

**结论**：
1. **glitch 主宰项消失**：total 从 1421fs 落到线性底噪 227fs（mode2）——按硅实测律，fbank 切换 glitch 不再是 jitter 瓶颈；前提是单元等效步进 ≤~77kHz（91fs/MHz 反推），**物理离散电容(≥5MHz 步进)做细bank仍被否决**，需 DAC+变容管/等效连续实现；
2. **新瓶颈=线性底噪，且 seed 敏感**：seed7 底噪 227fs，seed1 升到 ~343fs（+116fs）——TDC INL 实现与 DSM 交互的随机实现差异（此前噪声预算只报单 seed）；跨 seed 统计应成为后续预算的标准动作；
3. 底噪构成（seed7）：TDCq 149 + DSM泄漏 143 + DCO 128 + DTC热 80 + REF 25，实测 total 比 RSS(257) 低 12%（次可加）；到 200fs spec 的路径变为：DSM 泄漏（DTC 逐码 INL 查表）+ TDC 分辨率/热噪 spec + seed 鲁棒性。

## 1bit fbank 重评（2026-09-14 第四轮，`nb_1bit*.m`，13 run）

fbank 收缩为 **1bit（单单元=1 abank LSB，一阶 SDM 占空比平均）** 作为正式架构选项重新实现并仿真（mode0 与 mode2 双路径并存；单元测试 ALL PASS）。当前框架（真实 spec、4.84M 环路、**K=20**）下 13 个 run 对比：

| 项 | **1bit (mode0, K20)** | 3bit (mode2) |
|---|---|---|
| total σt（s7/s1/s3） | **1421 / 1450 / 1479** | 1421（s7） |
| 无 glitch 底噪 | **225.9** | 226.6 |
| glitch solo @100fs/code（4 seeds） | **1389–1402**（±0.5%，无轮盘） | 0.4–1394（轮盘，K32 数据） |
| glitch 扫参 10/200/300 | **12 / 2947 / 4490**（≥100 近线性 ~14–15×fs/code） | 0.4 / — / 4486 |
| 切换统计（total） | 8–12kHz, dstep=1 | 82kHz, dstep=3 |
| TDC 量化 / DSM 泄漏 | 135.0 / 156.5 | 148.8 / 143.2 |
| 量化相位纹波 | 3.7fs | 0.3fs |

**结论**：
1. **模型内 jitter 上两架构等效**（total/floor/glitch 标度全面重合，glitch 均 ~14×fs/code）——fbank 位数的取舍不由 jitter 决定；
2. **K=32 时 mode0 solo 0.7fs 的"安静轨道"是粒度假象**：坍缩码 = round(8·y_acc/K)，K=32 时占空比粒度 0.25 恰好冻结、K=20 时 0.4 步进持续跳变（solo 自激 50kHz/dstep=1/1394fs）；真实 K=20.0625 非整数，图案永不精确重复 → 活跃抖振才是代表性行为；
3. **物理 spec 锚点不同（关键提醒）**：模型 `fs_per_code` 按坍缩码变化计费——mode0 的"1 码"= 1/8 LSB 平均占空比变化 ≈ 大单元多切 ~1.5 个子步（≈12 个小单元等效的电容面积），mode2 的"1 码"= 恰好 1 个小单元切换。若模拟端按"每次单元切换"报价且 glitch∝面积，**1bit 的单单元大 8×，同一 fs/code 数字对应的物理要求苛刻 ~4–8×**；若 glitch 由驱动器主导（弱面积依赖），1bit 简单且够用。这是选型的决定性问题；
4. 其它权衡：1bit 省硬件（1 单元+1bit SDM vs 8 匹配单元+温度计译码）、纹波 3.7fs vs 0.3fs（均可忽略）；1bit 空闲音/杂散潜力更强（本轮 total 的 25M 杂散 −90 vs −90，未见恶化）。

诊断运行（不在预算内）：`tdc`（eq≡0 相位静止）→量化噪声退化为 0；`dsm`（理想TDC无抖动）→kdtc/g2 相关器确定性极限环 606fs 伪影（真实抖动下 kdtc 收敛 279.4、泄漏仅 ~55fs）。

## 闭环搭建期间发现的设计问题（建议转交 RTL/算法负责人）

1. **RM kdtc LMS 固定延迟2拍在 frac=0.25 反收敛**：周期4量化锯齿的半周期滞后使 cov(phe,eq_lag2)<0，任意增益误差下 kdtc 均被推离真值；正确对齐为 lag 0（phe(i) 携带 eq(i)，TDC mod-1 混叠吸收 DSM 超前一拍的整数差）。仿真 cfg 旋钮 `kdtc_lms_delay` 可复现（设 2 即重现反收敛）。
2. **funcs/lpf.m 将 ki 量化到 2^-10 网格**：ki<2^-10 会 round 成 0，积分器静默冻结、环路退化为 I 型（phe 出现持续 DC）。
3. **dsm_dco 必须自由运行**：adpll_fsm.v 未驱动 rstn_dsm_dco；FLL 期间若随 rstn_lpf 复位，细bank卡中间值 → DCO 只有整数分辨率 → FLL 死区 25MHz 永不锁定。且 dsm_dco 需按高速 clk_dsm 建模/实现——**clk_dsm = DCO÷4（复用 FLL fb_cnt 同源分频，8.025GHz 时 ≈2.006GHz），即每参考周期 FCW/4≈20.06 子步**（cfg `dsm_dco_oversample: 20`；曾按 32 近似，2026-09-14 修正）。ref 速率下 512 拍窗口计数噪声 ±80，freq_lock 无法判定。
4. **RM/dsm_dco_rm.m 直接以 lpf_frac 驱动 DSM 是占位错误**：均值偏 f/8 → abank 极限环。正确架构：8 个温度计码 = 1个abank LSB，DSM 输入 mod(8f,1) + 静态部分 floor(8f)（溢出折入 abank）。
5. **RM/RTL 不一致**：
   - `rtl/adpll/fll/fll.v` expected_count=FCW_int·2^thr 与 `funcs/fll.m` calc_cnt=FCW·2^thr/4 矛盾（模型隐含 fb 计数时钟为 DCO÷4 预分频；RTL 语义对应 DCO÷1 且 4bit thr 无法吸收分数部分）；
   - `adpll_fsm.v` ST_LOCK 态 rstn_fll=0 会清 freq_ctrl/freq_lock 使环路塌陷（仿真改为保持冻结，cfg `fsm_lock_keep_fll`）；
   - `funcs/lpf.m` 的 kp/ki 选择写反：spec 参数表与 `lpf.v` 注释均为 kp1=锁定前/kp2=锁定后，lpf.m 却在 phase_lock==1 时选 kp1/ki1（仿真 cfg 按 lpf.m 语义赋值，行为等价，仅命名相反）；
   - RM cfg `lock_cnt_thr:256` 是指数（2^256 永不锁定），顶层应取 ~8；
   - `RM/cfg/dco_duty_calibration_cfg.txt` 的 IND_sel_clk_fb 路径错指 IND_dco_dtc_comp.txt；
   - `rtl/adpll/pbank_afc.v` 的 !afc_calib_en 分支将 pbank_code 清 0 —— FSM 离开 AFC 态即丢失校准结果（仿真改为保持输出）；
   - `rtl/adpll/pbank_afc.v` 的 expected_count = trial_code<<8 是未完成的占位符（代码注释自认应为 FCW·window/N_divider），仿真按 spec 语义实现 expected = FCW/afc_div·2^afc_thr。

## 关键建模约定（TOP/output/*/README.txt 同步记录）

- **FLL fb_cnt**：计 DCO÷4 上升沿、2^9=512 拍窗口；喂 funcs/fll.m 采用脉冲约定（窗口首拍给真实计数、其余拍给 calc_cnt=25632 使误差为0），等价于 RTL 每窗一次积分（fll.v 的 ref_window_done_d）；保持式或实时式喂法经数值验证均发散。fll.m 首拍 calc_cnt_reg=0 有幽灵负误差，首个有效拍喂 0。
- **分频器**：tgt(k)=Σratio，恒等式 tgt(k)=k·FCW+eq(k+1)（单元检查验证误差为0）——DSM 量化相位被精确重构。
- **TDC**：残差 x=tgt−(phi+tau)（x>0=参考超前）；mod-1 回绕后量化到 1/256 周期；one-hot 编码与 pfd.m 解码严格往返（480 码全验证）。
- **DTC（2026-09-11 起 per spec）**：复用 funcs/dtc.m，dtc_lsb=1/280 周期（真值 kdtc*=280，初值300）；dtc_code=round((1+eq)·kdtc)+dco_dtc_comp。plant 附加：逐码 INL 2LSB RMS（平滑随机，相关长度64码，`dtc_inl_table`）+ DNL 1LSB RMS（非累积失配：累积型会把 INL 抬到 ~9×DNL，违反 2LSB spec，故 DNL 建成单元失配型）+ PN floor −160dBc/Hz@100MHz → σt=√(2·10^(L/10)·fref/2)/(2π·fout)=159fs 白抖动（单边 S_φ=2L、带宽取采样 Nyquist fref/2）。注意：`dtc_inl_table` 返回 LSB 单位，装配时必须乘 `dtc_lsb_cycles`（漏乘曾使 INL 放大280倍、phe 出现 ±0.25 周期周期-4 摆动、环路失锁；现装配处有 assert 保护）。
- **物理DCO（用户提供定义）**：pbank 6bit=30MHz频带/19.047619MHz间距（覆盖7.67~8.9GHz）；abank 9bit=511子带覆盖30MHz（LSB 58.7kHz）；**fbank 暂时 1bit**（`dsm_dco_mode: 0`：1单元=1个abank LSB，lpf_frac 全量进 1阶SDM {0,1}，均值=abank+lpf_frac；3bit 路径保留 `dsm_dco_mode: 2`，8码=1个abank LSB、DSM输入 mod(8f,1)+静态 floor(8f)）；f_dco = 7.67GHz + pbank·19.047619M + ctrl·(30M/511)。VCO标称8GHz。DCO 相噪 `pn_gen_1f3`：斜率可配（`dco_pn_slope_dbdec`，当前 10dB/dec=1/f），PSD 由单元检查10验证（±1.7dB）。
- **输出相噪分解（noise_budget.m）**：锁定段 e(i)=phi_abs(i)−i·FCW（DCO周期）线性去趋势后 Hann-Welch PSD（RBW 12.2kHz）；逐源单独运行（其余理想化：`tdc_ideal` 无限分辨率TDC / `dsm_fb_ideal` 理想分数分频 eq≡0 / DTC、glitch、ref_jitter cfg 关断），输出频率瞬态+相噪分解两张曲线与 σt/杂散汇总到 `output/noise_budget/`；total 运行即刷新 output/default。
- **AFC**：二分复刻 pbank_afc.v（trial 从32、步长32→1、min-|err| 记录）；DCO÷8 固定分频、2^7=128拍窗计数，expected=FCW/8·128；trial 仅在消费完窗口脉冲后更新（每窗测到稳定码）。
- **环路重整定（物理增益 Ka/fref=1/426）**：kp2=48（捕获段 pole≈0.11，可跟踪 FLL 残差斜坡且锯齿摆动可控）、kp1=1.664、ki=0.416、freq_lock_step=0、freq_lock_thr=6（±1.17MHz 残差交给 PLL 积分吸收）。
- 所有量化交接（phe/2^16、q_err/2^35、freq_ctrl/2^15、lpf_frac/2^26）与 RM IND/DBG 约定一致。
