# 项目状态 — UCIe-AP RX AFE（流片准备阶段：补电路 + 验证闭环）

> 恢复指引:本文件是跨会话状态记录。新会话从「环境与运行方式」恢复运行环境,
> 从「关键标定参数」恢复仿真配置,从「关键技术要点」避开已踩过的坑。
> 详细报告见 `docs/report.md`,论文规格提取见 `docs/spec_extracted.md`。

## 1. 当前状态（2026-09-03：P5 全部恢复完成）

**补电路（P0-P4）全部完成,验证闭环（P5）部分完成。** 目标:在功能验证基础上补电路+验证,向流片准备推进(版图/DRC/LVS 与数字综合仍在本期范围外)。

| 阶段 | 状态 | 关键结果 |
|---|---|---|
| P0 基线 | ✅ | BER=0,眼窗 229-353mV 复现 |
| P1 比较器 | ✅ | 二级线性增益(ulvt 对,一级输出→二级门极);连续锁存/StrongARM 两条再生路径**实测失败并记录**(见要点 10-11);眼高不变(输入受限) |
| P2 复制偏置 | ✅ | 最终版:2×16 fins lvt 二极管 + rhim 2.35µ + 16×cfmom 去耦,**平衡点 0.362V**;BER=0 |
| P3 R-2R DAC + TB 重构 | ✅ | **DNL 1.0 / INL 1.85 LSB**(近乎单调,code 127 处 −0.64 LSB 记录在案);`__MODELS__/__TEMP__/__VREFV__/__VBIC__/__NOISE_OPTS__/__NFDIO__` 占位符;封装模型(RS/LS/AMPL/FN) |
| P4 ESD | ✅ | nf=100(≈300fF/焊盘)零误码,nf=960 崩溃(拐点 100-960) |
| P5 MC 失调 | ✅ | **静态失调 σ=24.6mV、均值 −2.1mV**(200 runs 逐 seed 枚举);架构结论:此 AZ 只消漂移不消静态失配,失调由 vref 训练吸收(6σ=148mV < 眼窗 194mV);双 bank 独立失调差 σ≈35mV 是训练最大风险(未来工作) |
| P5 噪声冒烟 | ✅ | 器件噪声确认激活(on/off std 3.76mV/1e-16,无需 fnoise 段) |
| P5 Corner | ✅ 9-3 重跑 | **7/7 配置零误码**(温度机制修复+新鲜度门控后):tt25 90-200 / ff 90-210 / **ss 90-140(最差角,眼高 88mV,160+ 码 BER 13%)** / sf 90-210 / fs 90-190 / tt-40 90-190 / tt125 90-210 码;探针族 0.330-0.388V;所有角低边=90 码,高边收缩是唯一角效应,fs/-40 眼高 176mV 临界 |
| P5 TX Ron MC | ✅ 9-3 | 本地重解析 200/200(无需重仿,`scripts/reparse_mc_ron.py`):**Ron_pu 249.9±0.2Ω / Ron_pd 244.1±0.2Ω**(σ=0.1%,可忽略) |
| P5 噪声链路 | ✅ 9-3 | 冒烟 on std=3.81mV;链路 off/on_1/on_2 全 **BER=0**(0/639)——器件噪声在眼心不闭眼 |
| P5 电源 | ✅ 9-3 | 10/10 **BER=0**;100mV@400M 注入 vss_pk≈35mV(去耦+封装吸收);LS=1nH 键合线 vss_pk=398mV(PDN 振荡仍在,要点 13)但零误码 |
| P5 MC 失调重验 | ✅ 9-3 | 200/200 第 1 轮全过:**mean=-2.51mV σ=23.61mV**,与 9-2(σ=24.6mV)一致 → 要点 20④ 混合样本疑虑解除;6σ=142mV < 眼窗 194mV;旧结果备份 `tran_mc_offset_0902_backup.json` |
| P6 收尾 | ✅ 9-3 | 终跑有效(link BER=0/639 bits、眼图 194mV);plot_tran.py 扩展完成(tran_corners/tran_mc_offset/tran_mc_ron/tran_supply/dac_linearity 共 8 图);docs/report.md 已更新至流片准备版(§1/§3/§5/§6/§7) |

**当前链路基准(最新,含 ESD+真实偏置+封装模型)**:BER=0(639 bits),**眼窗 90-200 码 = 159-353mV,眼高 194mV ≥ 180mV 目标**。

## 2. 环境与运行方式

同前(无变化):21 服务器 / Spectre 25.1 / `virtuoso-bridge`(隧道 `virtuoso-bridge start`,在 pi_project 目录)/ venv python `/home/gmei/pi_project/.venv/bin/python` / 从 `afe/` 目录运行。

**新注意**:
- SSH 限流("Permission denied (password)"/"Connection reset")本轮频繁出现,还会**打挂 bridge 隧道**。对策:批量任务间 sleep 60-180s;隧道挂了用 `virtuoso-bridge stop && virtuoso-bridge start` 重置(旧 ControlMaster socket 会僵死,直接 start 不够,先 stop)。
- 并行统一 `max_workers=4`。

## 3. 关键标定参数（已烧入各 run 脚本）

| 参数 | 值 | 说明 |
|---|---|---|
| vref_code (VC) | 142 | 眼心附近(眼窗 90-200) |
| pi_code (PC) | 0.875 | 采样相位 |
| n_shift (NS) | 2 | 真 BER checker 流水线移位 |
| start_bit | 200 | checker 训练期(见要点 12) |
| VBIC | 0.362 | 偏置 ic = 2×16-fin 复制二极管的 DC 平衡点(实测) |
| NFDIO | 100 | ESD 二极管 nf(≈300fF/焊盘) |
| RS / LS / AMPL / FN | 0.5 / 0.01n / 0 / 100M | 封装模型;LS=0.01n 是安静基线(见要点 13) |
| MODELS | toplevel section=top_tt | corner 用 top_ss/ff/sf/fs;TEMP 在 tran 行 |
| VREFV | VC/255×0.45 | vref ic(训练期抽象) |

## 4. 关键技术要点(全部踩过的坑,勿重蹈)

1-9. 见旧版 status.md(自同步 checker 死链路、npode 二极管、binned nfin≈20.9、VCCIO 电流密度、laplace_nd、漂移注入节点、通道 z0=30、TX 延迟)——**全部仍有效**。
10. **连续导通交叉耦合锁存无法跟踪 16Gb/s**:正反馈记忆实测丢 21.7% 比特翻转(输入翻 83 次/输出只翻 65 次)。再生必须每比特复位(StrongARM 式),放在采样器位置,不在连续比较器里。
11. **StrongARM 采样器链路有系统失调**:单边 AZ 比较器输出共模随数据摆动,SA 输入对被 CM 伪影锁死(AC 耦合+vcm 偏置+ts 复位均未解决,实测恒单向判决)。真实 SA 采样器需要独立的时钟纪律设计(每比特复位、输入建立、失调校准)——已记录为独立未来任务,`tran/afe_sampler.scs`+`netlists/tb_sa_test.scs` 保留可复用。
12. **skipdc+ic 三连坑**:VA 块在 initial_step 读 V(vdd) 作摆幅 → 电源必须 ic(否则所有 VA 信号塌到 0.245V);偏置/DAC 的 decap×Zout τ 是 µs 级 → ic 必须给(且 nodeset 对受驱动节点无效,ic 有效);启动瞬态需要 start_bit=200 训练期(旧电路 100 够,新电路 6.3-10ns 全错)。
13. **PDN 振荡**:LS=1nH+片上去耦构成欠阻尼 LC 腔,实测 ±0.44V vss 弹跳(数据恒定时持续振荡,~150ps 周期)——这是真实的电源完整性问题,留待 P5 电源项系统记录。LS=0.01n(倒装级)是安静基线。
14. **复制偏置设计要点**:8-fin lvt 二极管的自然 Vgs 是 0.455-0.48V,会毁眼图(全网格 4+ 误码);2×16 fins 才把平衡点拉到 0.362V(32 fins 超 binned 上限,拆 2×16)。**复制器件应加宽而不是同尺寸**——输入对要的是低 Vgs 锚定点。
15. **AZ 架构语义**:此 ping-pong AZ 消**漂移**(周期重锚定),不消**静态 VT 失配**(AZ 把门极钉在 vbias,失配从未被感知/存储)。静态失调由 vref 训练校准吸收——论文机制一致。MC 测量的 σ=24.6mV 是训练要覆盖的失调分布,不是 AZ 失效。
16. **MC 流程坑**:①bridge 的 `sweep_points` 不解析 Spectre mc1 psfascii 布局(只有一个合并 tran 文件)→ 用逐 seed 枚举(`mc1 numruns=1 seed=k`,标准 tran 解析,400 任务 ≈ 15-25min);②usage.scs MC 段:`TTGlobalCorner_LocalMC_MOS/RES_BIP_DIO/MOM_MOSCAP`;**不能加 age0**(tmiAge=1 与 montecarlo 冲突 SFE-3226);③MC TB 的 eval 必须与 AZ 错开(重叠时 pA 被分压钉住,假失调 −43mV)。
17. **R-2R 位序**:输出端节点是 MSB(½ 权重),远端是 LSB;位序接反时 code=1 输出 212mV(应 1.76mV)。16-fin/4k 版本 DNL 5.7 LSB 且不单调 → 32 fins(2×16 并联)/6k 后 DNL 1.0 LSB。
18. **hia18 器件**:MOS 的 l≥135n(模型默认 118n 违反 Lmin);二极管 nf 面积 ~nf²(960→~14pF/只)。
19. **检查点纪律**:每步电路改动必须链路 BER=0 + 眼图重扫;改动 tran/va/template 文件前确认没有后台任务在跑(它们按任务逐个上传 include 文件,中途改文件=混合结果,踩过一次)。
20. **9-2 下午偏置事件与 P5 假失败**(2026-09-03 复查定位):corners/mcron/noise 运行期间 `afe_bias.scs` 处于坏/旧版本(偏置 DC 探针平衡点 0.458-0.499V,而非 0.362 设计点),17:15 修复后 biasdc_v3 验证 0.3621V、link/eye 终跑 BER=0。由此:①**每次 P5 批量跑之前先用 biasdc 探针确认平衡点=0.362**;②偏置 DC 探针 TB 不施加温度(tt@25 与 tt@125 结果逐位相同),温度角前须把 temp 写进 dc 分析;③bridge 对 mc1 包裹的 DC 结果提取失败(mcron 200 seed 服务器端全 PASS 但 `res.data` 取不到值),raw 已在本地 `output/mcron_*.raw/`,直接本地重解析;④`afecmp_bank.scs` 15:43 的改动落在 MC 失调运行中途(结果 15:53 出,include 按任务逐个上传)→ σ=24.6mV 疑混合样本,必要时重验。
21. **分析级 temp= 无效(2026-09-03 实证)**:dc/tran 分析行上的 `temp=` 参数对这些 TMI binned 模型**被静默忽略**——`dc1 dc temp=125` 结果与 25°C 逐位相同、psf 头部恒 27°C;正确机制是**命名 options 语句** `simOpts options temp=__TEMP__`(实证:-40/25/125°C 探针平衡点 0.3854/0.3627/0.3295V,头部温度正确)。两个模板已改;**此前所有标 TEMP=25 的跑实际都在 27°C**(差异可忽略,但温度角在新机制生效前从未真正跑过)。另:design 0.362 是 27°C 值,25°C 下为 0.3627(VBIC=0.362 烘焙仍然有效)。

## 5. 文件地图（新增部分）

```
afe/
├── status.md              本文件
├── docs/report.md         完整报告(待 P6 更新)
├── tran/
│   ├── afecmp_bank.scs    二级 AZ 比较器(ulvt 二级对+ulvt AZ 开关,nfin_sw=8,caz=80f)
│   ├── afe_tx_drv.scs     TX 驱动(未变)
│   ├── afe_sampler.scs    StrongARM+D-latch(未启用,未来任务复用)
│   ├── afe_bias.scs       2×16-fin 复制偏置 + 16×cfmom 去耦(rbias_l=2.35u)
│   ├── afe_dac_r2r.scs    8b R-2R(6k 单元,TG 2×16 fins,MSB 臂 -0.9% 微调)
│   └── afe_esd.scs        双二极管 ESD(nf 参数化)
├── netlists/
│   ├── tb_afe_tran.scs    主 TB 模板(__MODELS__/__TEMP__/__VREFV__/__VBIC__/
│   │                      __NOISE_OPTS__/__NFDIO__/RS/LS/AMPL/FN 占位)
│   ├── tb_afe_dac_dc.scs  DAC 单码 DC(逐码枚举用)
│   ├── tb_afe_cmp_mc.scs  失调 MC TB(ramp vin,__AZEN__/__NRUNS__/__SEED__/__EVALD__/__PANODESET__)
│   ├── tb_afe_txron_mc.scs TX Ron MC TB(dc,__NRUNS__/__SEED__)
│   ├── tb_bias_dc.scs     偏置 DC 平衡点探测
│   └── tb_noise_smoke.scs 噪声冒烟探针
├── scripts/
│   ├── run_tran_link.py / run_tran_eye.py   链路/眼图(默认 VC=142 PC=0.875 VBIC=0.362 NFDIO=100 LS=0.01n)
│   ├── run_dac_dnl.py     DAC INL/DNL(256 码枚举)
│   ├── run_tran_mc_offset.py  失调 MC(200 seeds 枚举,仅 az_on)
│   ├── run_tran_mc_ron.py     TX Ron MC(200 seeds)
│   ├── run_tran_corners.py    7 配置 × 2-pi × 13-vref(自带偏置 DC 探测)
│   ├── run_tran_noise.py      噪声冒烟+链路 noise=yes
│   └── run_tran_supply.py     电源注入扫描+LS 扫描
└── output/
    ├── tran_eye.json       最新眼图:90-200 码(159-353mV)
    ├── dac_dnl.json        DNL 1.0 / INL 1.85 LSB
    ├── tran_mc_offset.json σ=24.6mV
    └── tran_noise.json     冒烟通过(链路噪声数据待重跑)
```

## 6. 下一步（恢复会话后按序执行）

1. **P5 恢复已全部完成(2026-09-03)**——结果见 §1 表;恢复中新增的工具与修复:温度机制修复(要点 21)、`scripts/probe_bias.py`(跑前偏置探针)、`scripts/reparse_mc_ron.py`(本地重解析)、corners 脚本的子集重跑/合并/新鲜度门控。
2. **P6 已完成(2026-09-03)**:plot_tran.py 扩展 + docs/report.md 更新均落地。**P0-P6 全部闭环**,项目回到流片准备基线;下一阶段工作见 §1 表与 docs/report.md §7(ss 慢角优化/双 bank 训练/StrongARM 采样器/版图 DRC LVS)。
   **里程碑已存档**:提交「afe: UCIe-AP RX AFE 流片准备 P0-P6 全闭环（状态存档）」(70 文件;afe/.gitignore 白名单放行 10 图+11 个最终 json,raw/临时网表/大体积调试 json 留本地)。
3. 未来工作(已记录):双 bank 失调差的训练策略(σ≈35mV);真实 StrongARM 采样器(tran/afe_sampler.scs 复用);PDN 振荡的阻尼方案(LS=1n 下的 LC 腔);比较器在自然偏置点的再优化(如放弃 0.362 设计点);版图/DRC/LVS。
