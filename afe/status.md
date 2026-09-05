# 项目状态 — UCIe-AP RX AFE（流片准备阶段：补电路 + 验证闭环）

> 恢复指引:本文件是跨会话状态记录。新会话从「环境与运行方式」恢复运行环境,
> 从「关键标定参数」恢复仿真配置,从「关键技术要点」避开已踩过的坑。
> 详细报告见 `docs/report.md`,论文规格提取见 `docs/spec_extracted.md`。

## 1. 当前状态（2026-09-05：测试电路 n2s 全量落地+全 TB A/B 闭环）

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
| n2s 顶层组装 | ✅ 9-4 | 除数字行为级 5 个 VA leaf(symbol+stub schematic+磁盘 veriloga 源三件套)外全原理图化:afe_tb_tran 结构层(34 实例:6 VA+DRV/BIAS/BA/BB+8 TG MOS+信道 Rser/TL/Cxt/Crx+胶水源 12 个)+tb_afe_tran 顶层(24 实例:Xtb+电源/封装 R/L+cfmom 去耦×10+Xdac+Xesd×2+Xpc),schCheck 全 0 错;gate=si 导出对 golden 逐行(见要点 22-26) |
| 全链 golden link | ✅ 9-4 | **BER=0/639 bits、lock=0.801、vbias=0.3614**,功率对齐基线(DRV 326 vs 327µW;BA/BB 41.8 vs 43.9µW,vhi 微差级);网表=si 导出+组装归一(`output/n2s_top/golden_tb_template.scs`,scripts/gen_golden_netlist.py),仿真走服务器 21 |
| 全链 golden 眼图 | ✅ 9-4 | **90-180 码 × 全部 8 相位 BER=0**(基线内沿逐点一致,130/140 处 8/8 优于基线 7/8);190/200 码相位无关小误码(8/639、63/639)、210 码 8 点 SSH 限流失败(窗外,未重跑)——上边沿内缩 20 码的机制=golden vhi 锁存 0.770 vs 基线 0.968(din/ck 摆幅∝vhi,要点 24);vhi 硬化列入未来工作 |
| golden corners | ✅ 9-4 | 7 配置 6/7 零误码窗:tt25 90-180/ff **90-210(与基线完全一致)**/sf 90-200/fs 90-160/tt-40 90-170/tt125 90-200——上边沿伪影内缩 0-30 码与眼图同构;**ss 角全窗 84/639 误码**(相位与门限完全无关的固定子集=时序违约特征,机制=vhi 伪影链×ss 慢器件);**同平台同日旧网表复跑 ss=90-140 完全复现基线**→差异 100% 归因伪影链(网表等价性由混合实验证明),vhi 硬化升级为**流片前必做**;ff 首轮 23 点/±温探针为 SSH 限流失败,子集重跑已恢复 |
| 测试电路 n2s | ✅ 9-5 | **剩余 5 个模拟 TB 全原理图化**(tb_bias_dc/tb_noise_smoke/tb_afe_dac_dc/tb_afe_txron_mc/tb_afe_cmp_mc,afe_sch 现 24 cell);golden TB 网表=si 导出+组装(`scripts/gen_tb_golden.py`),网表级等价 5/5 PASS(subckt 器件集对 tran 源、顶层逐端口/逐节点);**A/B 对跑 9/9 MATCH**(`scripts/run_tb_ab.py`,本机 spectre 普通模式):bias 0.362723384V/DAC 3 码/cmp az_on trip/Ron_pu+pd 全部**位级一致**,noise_on 统计同量级(3.6/3.7mV,基线 3.76-3.81);MC 逐 seed 位级可比性靠要点 27 的发射序重排 |
| 全 TB n2s+快照+MC 重验 | ✅ 9-5 | **netlists/ 下 8 个 TB 全部原理图化**(补 tb_sa_test 6源+Xsa、tb_afe_va 单 Xtb;afe_tb VA leaf 三件套新建,`scripts/n2s_va_stub.py`);afe_strongarm/afe_dlatch 符号补齐+电源脚底边重布局(要点 28);**7/7 golden TB 等价验证 PASS**,A/B 累计 **11/11 MATCH**(sa_test/va_proto 位级一致);**全部 22 cell 快照至 `oephy/afe_0905/`**(含自含 cds.lib+README);**golden MC TB 本机 200-seed 全量重验 ALL MATCH**(`scripts/run_golden_mc.py`+`output/golden_mc_{offset,ron}.json`):失调 mean 0.07mV/σ 25.3mV(基线 −2.51/23.61,mean 差 2.58mV、σ 差 7.2%),Ron_pu 249.882±0.171/Ron_pd 244.143±0.175(基线 249.872±0.175/244.137±0.195,mean 差 0.004%/0.002%);同平台 legacy vs golden 逐 seed 位级一致(1..10 差 ≤1e-14V),跨平台逐 seed corr≈0=spectre MC 随机流版本依赖(要点 28⑤) |

**当前链路基准(最新,含 ESD+真实偏置+封装模型)**:BER=0(639 bits),**眼窗 90-200 码 = 159-353mV,眼高 194mV ≥ 180mV 目标**。

## 2. 环境与运行方式

同前(无变化):21 服务器 / Spectre 25.1 / `virtuoso-bridge`(隧道 `virtuoso-bridge start`,在 pi_project 目录)/ venv python `/home/gmei/pi_project/.venv/bin/python` / 从 `afe/` 目录运行。

**新注意**:
- SSH 限流("Permission denied (password)"/"Connection reset")本轮频繁出现,还会**打挂 bridge 隧道**。对策:批量任务间 sleep 60-180s;隧道挂了用 `virtuoso-bridge stop && virtuoso-bridge start` 重置(旧 ControlMaster socket 会僵死,直接 start 不够,先 stop)。
- 并行统一 `max_workers=4`。
- **2026-09-05:21 服务器整机不可达**(SSH Connection refused+ping 100% 丢包,非限流),本机 spectre 完整座位同源不可用 → 本日 TB A/B 走 `run_tb_ab.py --local` 普通模式;服务器恢复后跑批照旧走 common.make_sim。

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
22. **CDF 发射参数 DC-中性≠瞬态-中性(2026-09-04,全链 golden 首败根因)**:MOS/cfmom 的 CDF extras(w/multi/nf/sd/sa/sb/ploda/spot…)对 DC 探针全部中性(bias 0.36272V 逐位/dac 半码 23nV/esd IV 4e-16),但 Xpc 带 CDF 回调派生的 multi=20/nf=40(800 倍钳位)时 golden link **BER=0.34**:t=0+ 首步解被拖偏(vdd 0.8→0.404)→ VA `initial_step` 锁存 vhi=0.404 而非基线 0.968 → PI 相位 `tpi=125p×V(pi)/vhi` 偏 >¼UI → 全错码。处置:`gen_golden_netlist.py` 步骤 0 全局裸写归一(142 MOS+26 cfmom)。
23. **VA 支路地=全局 0 节点**:旧 afe_tb_tran.va 的 `V(codeb)/V(pi_in)/V(a_az_g)/I(gp_a)` 支路地是**全局 0**,不是 vss;胶水改用 analogLib 原语(vsource/vcvs/isource)时参考端必须接 0(组装层打点),接 vss 会改 t=0+ 回流路径(vss 首步 −0.1V vs 基线 +0.17V)。
24. **首步振铃平台相关,本机冒烟≠基线数值**:同网表 spectre 20.1(本机)/25.1(服务器)的 t=0+ 首步解不同(vdd[1] +0.075 vs +0.168);VA 的 vhi 锁存使全链对首步敏感。**混合对撞实验**(golden TB 层+旧 VA 包装=旧版本机逐位一致)是隔离差异层的手段;本机冒烟只验语法/收敛。
25. **si/符号机制(2026-09-04 沉淀)**:①veriloga 视图是 DM 文本视图,dbOpenCellViewByType 返 nil 属正常——VA leaf 三件套=「stub schematic(仅 pin,网表器可解析)+ symbol + 磁盘 veriloga 源」;②si 实例行按 stub subckt 头(字母序)发射,组装时重排为 module 声明序+注参数(G1 fbit/seed、CHK n_shift/start_bit 等);③afe_sch 无 tech→bind basic 后 pin/drawing、label purpose 可用(symbol 层无 symbol/drawing 层,	body=slection box);④label stub 方向=pin 对符号中心 |dx|vs|dy| 判定,密集符号必须锥区安全(X=y1+0.5,否则垂直 stub 跨脚短路);⑤si 导出前必须释放活会话 cv 写锁(关窗+dbClose),改过 cellview 必须 schCheck+dbSave(否则 OSSHNL-108/109);⑥hia18 MOS 的网表 nf 取 CDF `fingers`、multi 取 `m`——裸写 fingers=1/m=1/multi=1 后才与省略态一致;⑦analogLib vsource/vdc/idc/tline 的实例参数 CDF 通道写不进网表——TB 级激励值全部由组装脚本在导出网表上打点(与旧模板 __X__ 烘焙同构)。
26. **ESD nf_dio 参数化在原理图流丢失**:源 subckt `parameters nf_dio=50`+实例覆盖 100;n2s 把 subparam 默认 50 烧死。`n2s_tb.py fix_esd_nf` 按 golden 设计点烧 100(源默认 50 从未被任何 run 用过);NFDIO 扫描仍走旧网表流。
27. **TB n2s 与 si/本机跑批(2026-09-05 全部实证)**:①纯 net-label TB 的 schCheck 软告警是固有产物——golden tb_afe_tran 本身 (0 24)(告警按 symbol 来源分布:afe_bias 2/afe_dac_r2r 2/afecmp_bank 4/afe_tx_drv 0),叶子 cell 全 (0 0),**门=零错误**即可;②`simInitEnvWithArgs` 生成的 si.env 缺 simViewList/simStopList,必须手补(spectre 用 `si -batch -cdslib <cds.lib> -command nl`,本机 si 在 IC618 tools/dfII/bin/si);③si 发射 subckt 头**无括号**(`subckt afe_bias vbias vdd vss`)且 subckt 内器件与顶层实例都按**字母序**——解析/对比时按端口名映射即自洽;④**MC 失配抽签按网表元件发射序分配**:字母序 golden 与 legacy 同 seed 得到不同实现(cmp az_on 0.181→0.259);重排实验证明把 subckt 体恢复**源声明序**+顶层恢复 **legacy 声明序**(实例对序也互换实现,如 Xdrv_pu/Xdrv_pd)后**逐 seed 位级一致**(gen_tb_golden 1.5 步固化);⑤CLI `virtuoso-bridge eval` 的包装 .il 在本环境加载失败,一律走 Python client 写 .py 文件;⑥本机 license.dat 只有 SpectreBasic(完整 Spectre 座位在网络服务上):`+preset=ax` 卡 "Waiting for available license",**普通模式(无 preset)秒过且 A/B 等价性成立**(两边同模式);⑦common.py import 时把 afe/.env 的 VB_* 灌进 os.environ,本机模式构造前须清除再 chdir /tmp(run_tb_ab `make_sim_local`);⑧mc1 包裹 DC 的 res.data 取不到值(老坑 16③),txron Ron 用本地 raw `mc1_dc1.dc` 重-parse 回退。
28. **全 TB n2s 补遗(2026-09-05 下午实证)**:①**afe_strongarm/afe_dlatch 从未有 symbol 视图**——n2s_cells 期漏生成,此前无 TB 实例化故未暴露;`scripts/n2s_fix_symbols.py` 全库审计(schematic-有/symbol-无)+按 subckt 端口补建;②**符号电源脚垂直堆叠→标签桩跨脚短路**:vdd 正下方是 vss 时 vdd 的向下桩跨过 vss 脚,schCheck 报 2 错(DB-270004 "Can't tap \<vss\> from net vdd"+"Net vdd shorted to net vss")——要点 25④ 跨脚坑的实例;修法=电源脚放符号**底边水平展开**(向下桩远离一切引脚);③原生 schematic→symbol 生成的 SKILL 助手未随会话加载(undefined function),手工构建用包内 `symbol_create_pin/_selection_box/_label/_set_term_order`(0.25 节距、pin/label、instance/drawing 选择框);veriloga 视图=master.tag(40B 固定头)+data.dm(整文件复制)+.va 副本,纯文件层;VA leaf 引脚方向全 output(按 .va 模块声明),terms 回读用 `symbol_read_ports_skill`(裸 `cv~>terms` 对 symbol 惰性不物化);④删除带开窗 cell 会弹模态对话框阻塞 SKILL 通道(特征=30s socket 超时)→`virtuoso-bridge dismiss-dialog`(X11 通道)恢复;si 中途被杀会在 run 目录留陈旧锁(报 "Simulation is already running")→删 run 目录重新 simInitEnvWithArgs;⑤**spectre MC 随机流按版本/模式而异**:golden 本机(20.1+普通) vs 基线服务器(25.1+ax)同 seed 逐点 corr≈0,但分布(mean/σ)全对;同平台 legacy vs golden 逐 seed 位级一致(seed 1..10 差 ≤1e-14V)——**跨平台 MC 比对必须分布级,等价性证明用同平台逐 seed**;⑥si 导出带 afe_tb stub 的 tb_afe_va 时 gen_tb_golden 走 VA 叶片流(丢 stub def+Xtb 重排到模块声明序+注参数+头取 legacy ahdl 行),与 gen_golden_netlist 对 5 VA leaf 的处理同构。

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
│   ├── run_tran_supply.py     电源注入扫描+LS 扫描
│   ├── n2s_top.py         afe_tb_tran 结构层构建(34 实例+21 pin,从 /tmp 跑本地桥)
│   ├── n2s_tb.py          tb_afe_tran 顶层构建(24 实例+ESD nf=100 烧入)
│   ├── n2s_tbs.py         7 个 TB 构建(bias/noise/dac/txron/cmp/sa_test/afe_va,net-label+gnd!)
│   ├── n2s_va_stub.py     afe_tb VA leaf 三件套(stub sch+手工 symbol+veriloga 文件层)
│   ├── n2s_fix_symbols.py 全库 symbol 审计+缺失补建(电源脚底边布局防跨脚短路)
│   ├── gen_golden_netlist.py  si 导出→golden 模板(归一+VA 重排+胶水打点+directives)
│   ├── gen_tb_golden.py   7 个 TB 的 si 导出→golden 模板+等价验证(含 MC 发射序重排+VA 叶片流)
│   ├── run_tb_ab.py       legacy vs golden TB A/B 对跑(--local 本机普通模式通道,11 案例)
│   ├── run_golden_mc.py   golden MC TB 200-seed 本机重验(offset+ron,分布级判定)
│   └── run_golden_link.py / run_golden_eye.py  全链 golden 跑批(VA 5 文件为唯一 include)
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
4. **网表→原理图重建(2026-09-04 试点+全量铺开+顶层组装+全链 golden)**:客户端 virtuoso 技能 `references/netlist-to-schematic.md` 工作流(解析→CDF参数映射→确定性摆放→网络标号→三重验证门);**全部 7 个 subckt 建入 afe_sch 库(本机 IC618+tsmcN12,数据在 afe/virtuoso_ws/)**,逐 cell schCheck(0 0)+Gate B 回读+Gate C 回导网表逐设备位置节点元组一致:

   | cell | 实例 | golden |
   |---|---|---|
   | afe_bias | 19 | DC 探针 vbias=0.36272V 与源逐位一致 |
   | afe_pad_esd | 2 | IV 扫描(-0.5~0.85V)最大相对偏差 4.4e-16 |
   | afe_tx_drv | 36 | 网表级(超额参数均为已证中性类) |
   | afe_strongarm / afe_dlatch | 10 / 6 | 同上 |
   | afecmp_bank | 20 | 同上(analogLib cap/res 原语) |
   | afe_dac_r2r | 96 | code=128 半满码 vref 差 23nV |

   脚本 `scripts/n2s_afe_bias.py`(试点)+`scripts/n2s_cells.py`(批量,分块创建),产物 `output/n2s_*/`(netlist+bias 图)。**关键机制(全部固化进技能文档)**:①CDF 权威参数命名——MOS 是 `nFin`(网表 nfin/w 为推导值,直写被回调弹回),hia18 二极管是裸写 `nf`+`nfin=12`(模型省略态默认;摆放默认 8 非中性→电流 0.643×;w/l/multi 中性);②MOS 必须裸写 `sa=0/sb=0`(CDF 发射 sa/sb=90n 的 LOD 应力,+10.9mV 移动 0.362V 工作点;0=无应力哨兵,大值饱和不归零);③si 网表器不重算存量 prop;`set_instance_params` 的 geGetEditCellView 会漂(用显式 cv 批量更新);④Gate C 判据=位置节点元组;导出平铺网表+`\`续行+自带模型 include(外部 TB 勿重复 include);⑤>~200 行批量 SKILL 触发字面量栈溢出→分块创建(create+modify);⑥daemon 中断留下的半成品 cell 会引发会话恢复 SIGSEGV 崩溃循环(重启前删损坏 cell;afe/ 现有自含 cds.lib;.cdsinit 已修到 .local/state 新路径);⑦本机 spectre 20.1 可直接跑 12FFC 模型(golden 无需服务器)。
5. **顶层组装+全链 golden(2026-09-04 完成)**:afe_tb_tran 结构层+tb_afe_tran 顶层全原理图化(用户要求:除数字行为级外每模块原理图、顶层/测试程序均原理图);全链 golden link **BER=0/639** 与基线一致,眼图扫描见 §1 表;golden 模板 `output/n2s_top/golden_tb_template.scs`(si 导出+`gen_golden_netlist.py` 归一/重排/打点;MOS/cfmom 裸写、Xpc 裸写、胶水 gnd 参考、VA 实例重排+参数注入、directives 逐字);**要点 22-26 是本阶段全部新坑**。Virtuoso 会话中 afe_sch 库现含:7 cell(sch+sym)+5 VA(stub sch+sym+veriloga 源)+afe_tb_tran(sch+sym)+tb_afe_tran(sch)+va_probe/alib_probe(试验残留,可删)。
6. **测试电路 n2s+A/B 闭环(2026-09-05 完成)**:剩余 5 个模拟 TB(tb_bias_dc/tb_noise_smoke/tb_afe_dac_dc/tb_afe_txron_mc/tb_afe_cmp_mc)建入 afe_sch(净标签连接、gnd!→0、实例名=legacy 名;`scripts/n2s_tbs.py`);si 导出(先释放写锁+手补 si.env view/stop list)→`gen_tb_golden.py` 组装(0 归一化/1 激励打点/1.5 MC 发射序重排/2 头/3 directives 逐字)+网表级等价验证;`run_tb_ab.py` 9 案例 A/B 全 MATCH(bias/dac×3/cmp_on/Ron 位级,noise_on 统计,cmp_off 双 nocross 一致)。产物:`output/n2s_tb_golden/`(5 si 导出+5 golden 模板)、`output/tb_ab.json`(A/B 记录)。**要点 27 是本阶段全部新坑**。
7. **全 TB n2s+快照+golden MC 重验(2026-09-05 下午完成)**:tb_sa_test(6 源+Xsa)+tb_afe_va(新建 afe_tb VA leaf 三件套后单 Xtb 实例)建入 afe_sch;afe_strongarm/afe_dlatch symbol 补齐+电源脚底边重布局(要点 28①②);**7/7 golden TB 等价验证 PASS**,A/B 累计 11/11 MATCH(sa_test qp/qn 与 va_proto err/bit/lock 位级一致);全部 22 cell 快照至 `oephy/afe_0905/`(自含 cds.lib+README,rsync 排除 cdslck);**golden MC TB 本机 200-seed 全量重验分布级 ALL MATCH**(offset mean 0.07mV/σ 25.3mV vs 基线 −2.51/23.61;Ron_pu 249.882±0.171/Ron_pd 244.143±0.175 vs 249.872±0.175/244.137±0.195),同平台逐 seed 位级对照(1..10 差 ≤1e-14V)证明等价性,跨平台 corr≈0 定性为 spectre MC 随机流版本依赖(要点 28⑤)。产物:`output/golden_mc_{offset,ron}.json`。**要点 28 是本阶段全部新坑**。至此 netlists/ 8 个 TB 全部原理图化,原理图流全量替代网表流。
