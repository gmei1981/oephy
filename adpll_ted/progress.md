# 论文复现进度（JSSC 2021, Wu et al. 14nm 超低抖动小数 PLL）

更新: 2026-08-29

## 基础设施（已就绪）

- 21 服务器 spectre 25.10 + TSMC 12nm PDK，virtuoso-bridge 远程仿真链路全通
- 复用 /home/gmei/git/oephy/adpll（UCIe 6.2G 混合 ADPLL）的晶体管模块与 VA 数字模块
- 生成器: `scripts/gen_blocks.py`（10-bit DTC/解码器/双核VCO/模拟块）、`scripts/gen_top.py`（顶层）
- 运行: `scripts/run_bridge.py <netlist> [--stop 2u]`；本地快验用 `/home/gmei/bin/spectre`

## 与 base 的关键差异（论文特征实现）

| 论文特征 | 实现 |
|---|---|
| 10-bit DTC (Tres=330fs) | `inc/dtc_10b.scs` 1023 开关 RC DTC + `pll_dtc_decoder_10b.va` |
| 双核可重构 VCO | `inc/vco_dual.scs`（耦合开关 nf=64 + 核B供电 PMOS 开关，EN2 使能） |
| 修改型 MMD（半周期量化步长） | 复用 `pll_mmd_edge.va`（双沿计数 + SEL 半周期抖动 + MASH1-1） |
| 3×sign-LMS + 失调 DSM | 复用 `pll_lms.va`（kdtc/vdcc/rdcc/vref 四路） |
| 参考倍频器 76.8→153.6M | 复用 `pll_doubler_edge.va` |
| DTC 范围减半 | 解码器 QE→码: (epsc−(0.5−frac2))×(TVCO/2)/Tres，DR ±169ps 覆盖 ±1×TVCO |

## Step1 冒烟结果（300ns, 服务器, ok=True）

- 双核 VCO 起振 6.079 GHz（目标 6.2G，VCTRL 尚在捕获）
- CKFB 触发率 151.8 MHz = 40.36×TVCO ✓ 倍频模式采样栅格
- 校准四路（KDTC/VDCC/RDCC/VREF-ohat）后台并行自适应 ✓（与论文后台模式一致）
- SPD 斜坡/采样、比较器、GM 积分路径全部活动

## 排障记录（易错点）

1. **VA 编译**: ahdlcmi 需要每个端口显式 `electrical` 声明；`constants.vams`/`disciplines.vams`
   需与 VA 同目录（bridge 的 include_files 平铺上传，把两个 vams 头加入上传清单）
2. **VA 模块端口列表**: 超长单行（1023 端口 ≈6.5KB）会解析失败 → 每 16 端口折行
3. **spectre 多行实例**: 行尾必须 `\` 续行
4. **vcvs 桥接链**（base 的 Edec_i (cd_i,0,CODE_i,0)）在 1023 门时产生 Jacobian 零对角奇异
   → 解码器输出与 DTC 码端口同名直连，删除 Edec
5. **双核供电开关极性**: PMOS 开关栅极需反相使能（子电路内加反相器）

## 在跑

- VCO pnoise（双核/单核, PSS fund=6.1G, 10k-100M）→ 比对论文 −101/−98.1 dBc/Hz @100k
- DTC 码扫描（16 个码点 × 并行4）→ Tres/INL 比对 330fs/≤1LSB

## 下一步

1. DTC Tres 实测 → 调 R0/开关使 Tres≈330fs
2. 闭环 2µs+ 分段续跑 → 捕获轨迹、校准收敛顺序（VCO DCC→CKREF DCC→K_DTC）
3. 近整数通道 6451.3M 杂散
4. 抖动统计（tranNoise 或周期抖动法）比对 83.4fs
5. Step2: 100M/8G

## 2026-08-25 晚间进展

- **DTC 重设计**：变容管方案被否决（1023 关态栅电容垫底 ~1pF、C-V 非线性 INL ±数十 ps）
  → 改为论文 Fig.11a 的开关+电容单元。网格标定（本地 spectre）：nf=2、CLSB=0.5fF、
  R0=rhim 2.3µ×2µ → **Tres=336.9fs（目标 330 ✓）**，9 点 INL 窗口内最差 ±1.3ps（±4 LSB）。
  根因沉淀：大开关寄生电容主导、Ron≈R0 时高码段欠充、w=1u 时 VCR 恶化
- **VCO PN**（服务器 PSS+pnoise）：单核/双核 L(100k)=−77.3/−77.2 dBc/Hz（论文 −92@6G/−98.1@3G）
  - 无 3dB 双核改善：100k 处闪烁主导、两核闪烁相关不可平均；论文靠 Ls+LDO 抑制闪烁
  - 差距根因记录在案（设计简化：无 Ls 尾电感、无 0.5V LDO、0.8V 直供）
- **6µs 首跑失败**（下载被并行批次 SSH 挤掉→手动 scp 救回 1.76µs）：VCTRL 撞轨、环路发散
  - 根因 = 该跑用旧 497fs 变容管 DTC 与解码器 330fs 假设失配
- **速度优化**：解码器 1023 输出加 transition 50p 平滑（消除每周期硬阶跃 LTE 松弛）
- 排障：tran 文件 = plltran.tran.tran；pnoise 总噪 = chunk 末尾 "out" 值；SSH 限流

## 2026-08-25 深夜：环路不收敛根因链（已修复，等 1µs 验证）

1. **DTC 无复位** → 电容反灌电荷、环路中丢沿（CKDTC 76.8M）→ 加 CK2X 反相复位管 MRST_D
   （隔离动态码测试：153.6M 保持 ✓；探针：环路中 CKDTC 153.6M ✓）
2. **SPD 斜坡饱和**：VBSPD 直驱 PMOS 电流源亚阈值区 100mV 差 400× 电流（0.20→饱和 1.4V/ns、
   0.48→几乎关断）→ 改电流镜+rhim 38µ×450n 电阻偏置（I≈7.6µA），CR0 7fF→30fF →
   **实测斜率 0.216V/ns，3.25ns 窗口摆幅 0.7V 线性** ✓
3. vref0=0.25（斜坡中段）；单核直连 vco_x（避免掉电核B浮空节点拖慢收敛）
4. 本地仿真速率 ~15ns/min（1023 开关 DTC 节点数 2× 所致），1µs 验证跑预计 ~1h

## 2026-08-25 深夜续：倍频器根因修复（run1u 死环诊断）

- **症状**：1µs 验证跑 300ns 时 VCTRL 钉死 0V、VHOLD≈0 恒定、CKFB=75.7M（VCO 3.06G=目标一半）、
  斜坡周期 13.2ns（应为 6.51ns）且只在前 6.5ns 充电、后 6.5ns 复位。
- **根因**：`pll_doubler_edge.va` 在 REF 每个沿翻转 `ck_v`（0→1→0），输出只是 REF 的
  **76.8M 延迟复制**，不是 ×2！周期 13.02ns 的 CK2X → DTC → CKRST 使斜坡周期 13ns、
  充电窗 6.5ns（斜坡撞 0.8V 轨），采样网格（设计 153.6M）与斜坡错相 → VHOLD 恒 0 → 死环。
  旧注释"双沿触发修复倍频"只修了方向参数，未意识到"每沿翻转=延迟复制"。
- **修复**：改为定时器型 XOR 倍频——每个 REF 沿（升/降）输出高电平、3.25ns 后回落：
  CK2X 边沿距 6.51ns → 153.6M、50% 占空比。
- **链式验证**（REF→倍频→DTC(1023 码全开)→CKRST→SPD，80ns 本地跑 48s）：
  CK2X/CKDTCD=153.6M ✓；DTC 最大码延迟 290ps（设计 ~345ps，差 0.86× 由 KDTC LMS 吸收）；
  CKRST 高 3.15ns/低 3.35ns；**斜坡周期 6.50ns、摆幅 0.702V ✓**（设计 3.25ns 窗/0.7V）。
- **重跑 run1u**（1µs）：save 加 CK2X/CKDTCD/CKRST + writefinal="v1u.fc"；预计 ~2h。
  另踩坑：Spectre tran 的 ic 参数不接受多节点（`ic="a=1 b=2"`、`ic="a=1,b=2"`、
  `ic="a=1" "b=2"` 三种写法全部语法错）；`ic=all` 在 skipdc 下也不应用器件 ic。
  → 放弃 VI=0.55 加速，用原 `ic="OUTP=0.6"` 单节点写法。
- **捕获停滞根因 2（vref0 太高）**：新斜坡 0→0.68V/6.5ns 均值 ≈0.175V。采样 PD 环
  捕获的前提是 VREF < 斜坡均值（否则未锁时平均误差恒负、GM 积分钳 0、永无有效样本）。
  vref0=0.25（旧 13ns 斜坡几何遗留）→ VCTRL 停在 ~2mV（仅比例路径 0.06×VHF 瞬态）。
  base 可锁定环 vref0=0.05、near-int 网表 0.15 佐证。→ 改 vref0=0.15 重跑。
- **捕获停滞根因 3（谐波锁死）**：vref0=0.15 后 VCTRL 仍停在 0.002V、VI 恒 0、EBIT 恒 0。
  实测 CKFB≈76.4M（13.09ns）与 2×fref 斜坡栅格（13.02ns）近同步：VCTRL≈0 时
  VCO≈3.08G≈f_min，采样相位漂移仅 ~0.07ns/周期，400ns 内一直困在 3.15ns 宽的复位区
  → VHOLD 恒 0.001 → 自洽死锁平衡点（VHF=0.035 固定点）。base 无此问题（Nint2=161，
  CKFB=38.4M，拍频 38M，26ns 即扫完斜坡）。→ 加 Iinj pwl 电流源 0-2ns 注入 550µA
  预充 VI≈0.55V，环路从近锁定状态启动（与论文 Fig.10 从初始误差收敛的场景一致）。
  又踩坑：isource 正值为拉出首节点电流（SPICE 惯例）→ 充电须用负值；
  type=pwl wave 时间解析异常（等价 2s 脉宽）→ 改用
  type=pulse val0=0 val1=-550u width=2n period=1m，standalone 验证 VI: 0.55V ✓。
- **MMD 分频比根因 4**：预充电后 VCTRL=0.55 稳、VCO≈6.2G（FFT 确认 OUTP/MMDIN 均 6.2G、
  缓冲链不降频），但 CKFB=77.5M=6.2G/80，非预期的 153.6M。standalone 验证：
  VA 的 CKFB 每个 cnt_target 计数翻转一次、方波周期=2 次翻转 → **等效分频比 = Nint2+frac2**
  （不是设计文档误写的 (Nint2+frac2)/2）。base Nint2=161 → CKFB=fVCO/161.5=38.4M=fref/2
  子谐波锁定，所以从没暴露。修正：step1 Nint2=40/frac2=0.364583（CKFB=6.2G/40.36=153.6M ✓
  =论文 CKFB），nearint 42/0.000651，step2 80/0；gen_top.py CONFIG 同步修正。
  （注：base/smoke 的 "CKFB=151.8M" 报告与 VA 实际行为不符，以本次 standalone 实测为准。）

## 2026-08-26 凌晨：1µs 闭环首次正确锁定 + 续跑中

- 四根因全修后 1µs 跑完成（0 错误，1h35m）：**CKFB=155.0M 全程稳定**、VCTRL 平坦
  0.554-0.560、采样点呈 ~0.001/~0.126 双值模式、四路校准活跃（KDTC 0.98→1.13、
  RDCC −12.7→−19.8、VREF 0.152→0.137 先降后稳）。
- 开放问题：CKFB=155.0M 比目标 153.6M 高 0.9%（fVCO≈6.256G），未精确拉入。
  机制：模拟 GM 对斜坡均值无鉴频，拉入靠比例路径调制不对称性，与失调 DSM 的 VREF
  自适应互相牵制。需更长时间数据判断是否向 153.6M 收敛。
- 已用 v1u.fc 分段续跑至 3µs（readic+skipdc 秒起，~4-5h），监控每 200ns 报
  VCTRL/CKFB/VREF/KDTC。run_local_segment.py 新建（本地续跑工具；修了两个 bug：
  f-string 反斜杠语法、SameFile 拷贝）。

## 2026-08-26 上午：3µs 续跑数据诊断 + Iinj 重触发根因（已修复，探针验证中）

- 昨晚 3µs 续跑（03:48 起）跑到 **t=1.73µs 被机器重启打断**（07:32 停止，无新 checkpoint）。
  对已存 run3u_cont 数据的完整诊断：
  - **fc 恢复是位精确的**：t=0 时 VCTRL=0.5569（fc 值 0.5569 ✓）、VI=0.5524 ✓
  - **但 VCTRL 在 2.4ns 内从 0.557 跳到 1.110**，随后整段 1.73µs 在 1.11→0.97 缓降。
    根因：`Iinj`（0-2ns 550µA 预充电脉冲，period=1m）在续跑 t=0 **重新触发**，
    把 VI/VCTRL 再泵 +0.55V。启动专用激励在续跑中会重放——与 ic 恢复正交。
  - 有趣物理发现：即使 VCTRL≈1.0V，**fVCO 仍 ≈6.28G**（OUTP FFT、MMDIN 沿计数，
    100ps 采样混叠到 3.8G）且 CKFB 全程 154-157M——变容管 C-V 非单调
    （0.555 与 1.0V 两侧同电容值），环路在反型支上找到另一个自洽平衡点。
    这解释了为什么该续跑"看起来还锁着"但 VCTRL 明显异常。
  - 修复：`run_local_segment.py` 增加剥离启动专用激励（正则删 `^Iinj` 行）；
    已生成无 Iinj 的 cont 网表（grep 验证 ✓），50ns 探针跑验证中。
- 探针通过后从 v1u.fc 重启干净 3µs 续跑（后台），监控 CKFB 155→153.6M 收敛。
- **50ns 探针结果 ✓**（5m04s，0 错误）：VCTRL 全程 0.5557-0.5571（无跳变）、VI 恒 0.5524、
  CKFB 周期 6.5ns=153.8M、SPD 斜坡 6.5ns 周期正常 → Iinj 剥离修复有效。
  已启动 stop=3u 干净续跑（raw=run3u_clean，预计 5-6h，ETA ~15:45）。
- **近整数通道（6451.3M）已上 21 服务器**（ax 模式，1µs）。踩坑：桥接 SSH ControlMaster
  中途 connection reset → 下载失败报 ok=False，但远端 spectre 成孤儿进程继续跑（99% CPU）。
  `virtuoso-bridge restart` 已重建隧道；用 sshpass scp 手动取回（沿用 base 项目救回路径）。
  部分数据（0.37µs）健康：VCTRL 0.555、VI 0.553（预充电 ✓）、四路校准自适应、
  CKFB 146.7M 上拉中（双核 VCO 调谐略异，锁定 VCTRL 预计 ~0.59）。

## 2026-08-26 上午续：近整数 1µs 完整分析 —— GM 积分路径失效根因

- 近整数 1µs 跑完（0 错误，13m49s，350MB 数据）：**CKFB=146.6M（目标 153.6M）未拉入**，
  且 0.5-0.95µs 从 147.5M 漂向 145.0M（错误方向）。VCTRL 钉在 0.555（=Iinj 预充电值）、
  VI 全程 0.5523-0.5528 几乎不动、EPSC 有界（纯 QE 量化，不代表锁定）。
- **根因（电路级）**：gm_x 输入差分对是 svt NMOS（Vth≈0.35V），而 VHOLD/VREF 工作点在
  0.05-0.15V → 深度亚阈值，GM 输出仅 ~1-2nA（base 项目 "v2 fix" 注释即为 1.9nA 量级）。
  1.9nA/2pF ≈ 0.95mV/µs → 拉入近整数所需 VCTRL +35-50mV 需要 35-100µs，
  1µs 仿真只看到瞬态开头。主通道同样机制（155.0M vs 153.6M 的 0.9% 残差、VCTRL 平）。
  base 项目能锁（VCTRL 0.645）是因为其 38.4M 几何下采样相位 38M 拍频扫全斜坡、
  均值 0.175 >> VREF 0.05 → 正向大误差强拉；本复现 153.6M 几何预充电后拍频仅 1.4-7M，
  采样簇拥在斜坡低段（VHOLD 均值 0.04-0.047 < VREF 0.14）→ 错误方向微拉。
- 决策点：GM 提速（ulvt 输入对 / 提斜坡电平与 vref0 / 提镜像比）vs 先实测各通道
  平衡点（更长跑）vs 预充电按通道重调。见用户选择。
- **用户指示：服务器并行多方向测试**（48 核足够）。已生成 `scripts/gen_variants.py`
  并上服务器 /tmp/gmei_nearint/ 同时跑 5 个变体（各 +mt=8，ax 模式，带 100ps strobe）：
  | 变体 | 改动 | stop |
  |---|---|---|
  | A_base | 基线（平衡点探测） | 4µs |
  | B_ulvt | gm_x 输入对 MN1/MN2 svt→ulvt | 2µs |
  | B2_lvt | gm_x 输入对 svt→lvt | 2µs |
  | C_prechg | Iinj 预充电 550µ→600µA（VI≈0.60≈锁定点） | 2µs |
  | D_mirror | gm_x MP2 镜像 72n→16n（拉电流 ×4.5） | 2µs |
  5 进程已确认在跑；监视器轮询完成态，完成后 scp 回本地分析。

## 2026-08-26 上午续2：根因定位于 VCO 无调谐范围（moscap 台阶式 C-V）

- **变体结果汇总**（服务器 2µs 闭环，均 0 错误）：
  - B_ulvt：VCTRL 0.54→0.476（GM 活跃了，方向反：VHOLD 均值 0.045<VREF 0.14）
  - B2_lvt：VCTRL 缓慢下滑 7mV；C_prechg（VI=0.60）：VCTRL 平 0.605；
    D_mirror：VCTRL 缓升。**所有变体 CKFB 都钉在 145-147.5M，VCTRL 动 60-70mV
    频率纹丝不动** → VCTRL 没有频率权威。
- **VCO 调谐曲线实测**（48+42 个独立 TB，服务器并行）：T0 坦克 fVCO 对 VCTRL
  完全平坦（vco_x 6.25G / vco_dual 6.25G，仅 VCTRL≈0 有 4% 台阶 6.00G）。
  PDK 定义 moscap_rf(gate bulk gnode)，C-V 是 ~0.2V 宽的陡台阶（台阶位置 VCTRL≈0.1），
  工作区 0.2-1.0V 全在 Cmin 平台 → **KVCO≈0**。这是主通道 0.9% 残差、近整数拉不进的
  真正根因（此前归咎 GM 亚阈值只是次要因素）。RF 模型按直流偏置取 C，无摆幅平均，
  台阶不会自然展宽。
- **接法变体全测**（gate/bulk 互换、nw 器件、±0.2/0.4V bulk 偏置、150fF 串联）：
  只能平移台阶位置（偏置 −0.4V → 台阶挪到 0.2-0.4V），宽度不变，做不出可用 KVCO。
- **方案：论文同款多单元错位偏置阶梯变容管组**（5 单元 × bulk=VCTRL−(0.2+0.1k)，
  台阶 0.3..0.7V，阶梯 KVCO）。批次 3 在跑：3 种单元尺寸（KVCO≈625/310/160 MHz/V）
  × 单核/双核/近整数坦克（nr=179）。选型后改 vco_dual.scs 重跑闭环。
  （论文 KVCO_I≤80 MHz/V 由 5/3-bit 组可编程；本复现取 160-310 MHz/V 档。）
- **批次 3 结果**：首轮因 OUTN/OUTP 两组偏置实例重名全部报错（SFE-401），修复命名后
  40/40 完成。但 0.1V 偏置间距小于 moscap C-V 台阶宽度（~0.1-0.2V）→ 所有单元台阶
  重叠成一个大台阶：fVCO 5.00G@≤0.2V → 5.25G@0.3-0.8V → 5.50G@1.0V（非单调两段）。
  另发现：5×wr110n 单元的 Cmin 比原单管（wr538n）大 ~109fF（护栏寄生按实例数计），
  坦克需同步缩容补偿。偏置偏移效率 ~0.5×（−0.4V 偏置 → 台阶 +0.2V）。
- **批次 4 在跑**：4 单元 × 0.3V 间距（偏置 −0.3..−1.2，台阶预计 0.25-0.7V）×
  4 个坦克配置（vco_x/dual × CF nr 192/160/144），VCTRL 0-1.0V 每 0.1V 一点。
- **A_base 4µs 基线完成**：近整数无改动平衡点 = CKFB **146.7M 恒定 4µs**
  （fVCO=6.161G，低于目标 4.5%），VCTRL 冻 0.555、VREF→0.137、VDCC→26 收敛、
  KDTC 0.72-0.83 抖振。1µs 跑看到的 147.5→145M 只是向平衡点的瞬态，不是谐波锁死。
- **直接 C-V 实测**（98 点 × 2 器件，1GHz 小信号电流源 + 1MΩ 隔离电阻）：
  moscap_rf C(VB) = 25.4fF@VB≤−1 单调缓降 → 18.8fF@+0.45V → 陡降到 4.0fF@+0.8V
  （Cmax→Cmin 过渡在 Vgb=0.35→0）。按此曲线 VCO 本该有 100-170MHz 调谐，实测平坦
  → **moscap_rf 模型在 VCO 真实 RF 工作条件下电容锁定在 Cmin、无偏置依赖性**（RF 模型
  频率效应；1GHz 小信号测出的 C-V 在 6GHz 大摆幅下不适用）。
- **批次 4/5 结论**：阶梯 moscap（0.3V 间距）与晶体管变容管（NMOS 4 种 bulk 偏置、
  PMOS，G=VCTRL、S/D=坦克）**全部平坦无调谐**。5 个批次穷举证明该 VCO 工作点
  （6GHz、坦克 DC=0.8V）没有任何可用 KVCO。
- **决策：退路方案 A**——零 KVCO 简化 + 按通道重调固定电容组（论文本身用 5b+31b
  分立组做通道选择，连续 KVCO 仅 ≤80MHz/V 对付 PVT 漂移；固定 PVT 下零 KVCO 是
  可记录在案的复现简化）。标定目标（插值 T 批次数据 + 实测平衡偏移）：
  主通道（单核，平衡=standalone×1.012）nr≈200；近整数（双核，×0.986）nr≈173。
  每通道 1µs 服务器跑 2-3 轮迭代标定。
- **本地 3µs 主通道续跑完成**（干净续跑 5h，0 错误）：CKFB 起始 151M（MMD 重同步
  瞬态）→ 0.5µs 后**恒定 155.0M 至 3µs**，不向 153.6M 收敛（昨天开放问题答案：
  稳定错误平衡，无收敛）。VHOLD 窗口均值 0.03↔0.10 以 ~0.7µs 周期振荡 = CKFB 与
  153.6M 网格 1.4MHz 拍频的采样相位慢扫证据。校准仍在慢收敛（VDCC 9.7→24、
  RDCC −13.6→−38、VREF→0.104、KDTC 0.96-1.18 抖振）→ LMS 时标 ~10µs 级。
- **Plan A 第一轮标定已上服务器**：cal_main_nr200（单核）/ cal_nearint_nr173（双核）
  各 1µs 并行跑，监视器就位。预期 CKFB 落在 153.6M ±0.5%。
- **主通道标定收敛（3 轮）**：nr=200→151.91M、nr=197→152.94M（周期法精度 ±0.02%，
  灵敏度 +0.34MHz/单元）、**nr=195→153.63M ✓（误差 0.02%，标定完成）**。
  注：0.2µs 窗口沿计数法精度仅 ±5M，前两轮误读为"152.5M 没变"；改用全窗口
  边沿周期均值后分辨率足够。近整数 nr=173 4µs 延长跑进行中（确认平衡点）。
- **近整数 nr=173 标定命中（4µs 跑）**：CKFB 153.60→153.52→153.24M（三窗口），
  就在目标 153.6M 上 ✓。但观察到：VCTRL 降到 0.448（GM 在新几何下被拉下 107mV）、
  VREF 升到 0.26、VDCC 走到 −122、RDCC −66——校准路径在坦克重调后的新采样几何
  下重新收敛（与 nr=192 基线的工作点完全不同）。CKFB 缓滑 −0.18M/µs 疑为 VDCC
  收敛瞬态，已启动 8µs 验证跑确认稳定性（~2h）。
- **8µs 验证跑完成**：CKFB 前 4.5µs 从 153.60 缓降至 **153.01M 后恒定 3µs+**——
  平衡点稳定在 153.01M（−0.38%），缓滑确认为校准瞬态（4µs 快照的 VREF 0.26/
  VDCC −122 到 8µs 恢复为 0.143/+15.7 良性值）。按 0.37MHz/单元 → **nr=172**，
  已启动 5µs 精标跑（~70min）。RDCC 仍在慢收敛（−66→−93）。
- **杂散方法学**（spur_analyze.py，8µs strobe 数据验证）：100ps strobe 量化把相位
  谱本底抬到 ~−60dBc/bin（359kHz 分辨率），论文级杂散（<−73dBc 音）被淹没、峰群
  全为分辨率假峰 → **需精采样重跑**（maxstep=2p 全保存、无 strobe，边沿插值
  ~0.1-0.2ps）。nr=172 定稿后启动 10µs 精采样杂散跑（~2.5h）。

- **0827 接续**：昨晚 18:32 备好的三个 staging 均未实际启动。今晨启动 nr172_5u 与
  nr195_5u，初用裸 `+mt` 上服务器发现单核运行（99%CPU，0.75µs/h，昨日 bridge 默认
  `+preset=ax +mt` 有 4µs/h）→ 2.5h 后杀掉改用 `+preset=ax +mt` 重启（srf 跨模式
  recover 被拒 SPECTRE-4076，从 t=0 重跑，ax 后 749% CPU）。10µs 精采样 staging
  （近整数 nr172 + 主通道 nr195）已预上传服务器待命。
- 抖动双口径脚本就绪：jitter_analytic.py（VCO PN 曲线高通过 fc 积分；paper 基准
  −92@100k f^-2 口径自检 = 103.7fs ≈ 论文 83.4fs 同一量级 ✓）；实测口径用
  spur_analyze.py（CKFB 相位序列 PSD → rms jitter）+ jitter_analyze.py（OUTP 过零）。
  解析口径预跑：双核 VCO PN → 260.5fs（fc=1.2M；fc=100k 灵敏度 2029fs）vs 论文 83.4fs，
  差距主要来自 10k-1M 段闪烁（L(10k)=−49.4 vs 论文 f^-2 的 −72）。
- cal_measure.py：strobe 数据 CKFB 边沿周期均值测频（100ps 量化/√N → ±0.016%）。
  旧数据自检：8µs nr173 跑 → 153.0293M（−0.37%，nr 步 −1.54 → nr=172 ✓）；
  主通道 nr195 1µs → 153.6285M（+0.019% ✓）。

- **0827 标定判定（5µs AX 跑）**：近整数 nr=172 → CKFB **154.0004M（+0.26%）** 全程稳定、
  VCTRL 0.553；nr=173（8µs 旧跑）→ 153.0293M（−0.37%）→ 双核坦克灵敏度实测
  **0.97MHz/单元**（主通道 0.37 的 2.6×），目标插值在 nr≈172.4，整数码撞不到 ±0.02%，
  nr=172 为最接近。主通道 nr=195：1µs 跑 153.6285M → 5µs 跑 **153.1905M（−0.27%）**，
  −0.44MHz 状态依赖漂移（VCTRL 0.555→0.439 缓降，残余调谐 ~4MHz/V；LMS 各路径 5µs
  仍在游走：RDCC −14→−63、VDCC ±80 大摆幅、KDTC 0.5-1.4 振荡）。结论：Plan A 标定
  残差 ±0.3%（整数 LSB + 状态依赖双因素），CKFB 锁定稳定、绝对频率记录在案。
- 10µs 精采样双跑已上服务器（AX 模式 684% CPU，近整数 nr172 / 主通道 nr195，
  save OUTP/CKFB/VCTRL），~2h 后出杂散+周期抖动数据。

- **0827 10µs 精采样分析（Step 1 收口）**：
  - CKFB 10µs 全程恒定：近整数 153.9842M（+0.25%）、主通道 153.2805M（−0.21%），
    与 5µs 判定一致 → 标定残差 ±0.3% 定稿（注③口径）。
  - **主通道小数杂散 f_frac=56MHz 处 −72.9 dBc ✓（论文量级）；参考杂散 −59.5 dBc**
    （论文 −69.6 最差角，差 ~10dB）。
  - **近整数小数杂散不可比**：100/200kHz 相位摆动 >0dBc（±UI 级，KDTC 0.5-1.4
    不收敛 + 零 KVCO → 采样相位扫全斜坡，PD 近周跳），Plan A 局限记录在案。
  - 抖动：周期抖动实测 96.7fs（近整数）/106.6fs（主通道，cycle-to-cycle 口径）；
    解析口径 260.5fs（口径自检 103.7fs）；相位解调积分含确定性分量不作比对口径。
  - comparison_report.md 定稿（"Step 1 完成"）；Step 2（100M/8G 整数通道）未启动。

- **0827 Step 2（100M/8G 整数通道）启动**：冒烟 300ns 通过（fVCO=7.926G −0.92%、
  CKFB≈fVCO/80≈99M、缓冲链全速翻转、OUTP 摆幅 2.01Vpp）；1µs 标定双点并行
  （nr=188 → CKFB **100.0000M 周期恰 10ns 锁定** ✓、nr=187 → 100.266M 括住
  灵敏度 0.266MHz/nr）；10µs 精采样跑（nr=188）已上服务器（AX，~2.5h）。
- 坑：ssh-agent 失效导致 21 服务器 key 认证被拒（"Permission denied (password)"），
  **改用 -o IdentityAgent=none -i ~/.ssh/id_ed25519 直连恢复**；rsync 同理加
  -e "ssh -o IdentityAgent=none -i ..."。

- **0828 Step 2 收口**：10µs 精采样（nr=188）分析完成——CKFB 10µs 均值 99.6582M
  （−0.34%，10µs 内 100.0→99.58M 缓滑，VCTRL 0.56→0.40 状态依赖与 Step 1 同型）；
  fVCO 均值 7.9727G；**参考杂散 −63.4 dBc @100M**（2f_ref −65.2，比 Step 1 −59.5
  好 4dB，距论文 −69.6 差 6dB）；周期抖动 152.9fs（8G）。整数通道无小数杂散 ✓。
  comparison_report.md 定稿（Step 1+2 完成）。

- **0828 网表→原理图转换项目（进行中，状态快照供续跑）**：
  - 工具（tools/）：sch_pilot.py（vlink parse AST → 角色分类 → 列布局 → SVG 预览）、
    gen_sketch.py（SKILL 生成器：实例/pins/布线规划 + 括号平衡自检）、cmp_x.scs/ast.json。
  - 角色分类已正确：cmp_x 7 器件（差分对/尾管/二极管负载/镜像负载/输出推拉）。
  - **已验证可用的 SKILL API**（IC25.10 与 IC618 均适用）：
    dbCreateInstByMasterName(cv "tsmcN12" "<master>" "symbol" "<name>" <x>:<y> "R0")
    ——原点是点、朝向是字符串（旧式 transform 列表形式报 Invalid origin）；
    本机 IC618 设参用 dbReplaceProp(inst "l" "float" 1.6e-08)（`~>` 赋值在本机报错，
    21 的 IC25 上 `inst~>p=v` 可用）；dbCreateNet/dbCreateLib/dbOpenCellViewByType/dbSave 正常。
  - **SKILL 陷阱**：`t` 是布尔常量不能做 let 变量；`>=` 前缀形式是语法错误（用 greaterp）；
    `>` 是特殊字符；本机 .cdsinit 加载 RAMIC 桥（-nocdsinit 不影响签名）。
  - **cmp_x 已绘制并验证**：本机 virtuoso_ws/adpll_sch/cmp_x（7 器件全参数已写入、
    SKILL 查询验证坐标/类型/l 读回 ✓）；21 服务器工作区已 rsync 回
    server21_sch_backup/（IC25 cellview 存档，本机 IC618 打不开）。
  - **阻塞：schCreatePin/schCreateWire/schCreateWireLabel 的新版签名未攻克**（两类机器、
    有无 cdsinit、经典/扩展参数/底层 db 原语、method/glue 各种值全试过）：
    pin 第 2 参要 net 对象（第 6 参 list、第 7 参 string）；wire 带 method/glue 参数
    （SCH-1001 报无效值，string/symbol/t/nil 均被拒）；label 要 ≥9 参。
  - **下一步候选**：① xdotool 在 :0 驱动 Virtuoso GUI 画一根线 → 读 CDS.log 提取
    GUI 记录的正确 SKILL 语法（无需用户操作）；② 用户手动在 GUI 连线；③ 交付
    器件摆放 + 布线清单。SPD/GM/VCO 核的摆放管线已就绪（同一生成器）。

## 2026-08-29 存档：原理图转换模块清单 + 手动绘制方法论（本会话状态）

- 本机原理图库确认就绪：`virtuoso_ws/adpll_sch`（cmp_x 已摆放 7 器件+参数读回验证，
  缺 pin/连线；lt3/lt4 为 pin/wire API 试验 cell）；cds.lib 在 `virtuoso_ws/cds.lib`
  （basic/analogLib/tsmcN12/adpll_sch；adpll_sch 重复 DEFINE 无害，取第一条）。
  21 服务器 IC25 副本在 `server21_sch_backup/adpll_sch`（本机 IC618 打不开）。
- **待转模块清单**（netlist/inc/）：spd_x(7 器件：MIR+RREF 偏置、MCS 充电镜像、
  MSMP 采样 nf=8、MRST 复位 nf=32、CH 保持 cfmom nr=12、CR0 斜坡 30f)、
  gm_x(6：NMOS 对 nf=1 + MTAIL + MP1 二极管/MP2 镜像负载，**MP2 l=72n** 余皆 16n)、
  vco_x(16：交叉耦合对 nf=16 + 2.49nH 电感 r=2 + 12×cfmom nr=192（中间浮空节点
  net8-16 须保留）+ 2×moscap_rf wr=538n)、vco_dual(8+2×vco_x：EN2 反相器 +
  MPWRB 供电开关 nf=64 + MSWP/MSWN 耦合开关 nf=64)、vco_dual_8g(同构，1.5nH)、
  dtc_10b(R0 rhim 2.3µ×2µ + CKXB 反相器 + MRST_D 复位管 + 1023×(开关 nf=2 +
  CLSB=0.5fF 电容)，1027 端口)。
  VA 模块（mmd_edge/lms/dtc_decoder_10b/hybrid_aux）纯行为级，只需建 symbol。
- **scs→原理图规则沉淀**：MOSFET 节点顺序恒为 D G S B（bulk：pch→VDD/nch→VSS）；
  电阻/电容/电感 (+ −)、cfmom (+ − shield→VSS)、moscap_rf (gate bulk)；
  scs 参数即 CDF 名照抄（nf/nfin/multi 是 pcell 参数，不拆器件）；
  不在端口列表的节点 = 待命名内部 net（TAILN/OUTP1/VBSPD_M/VDLY/UCAP<n>…）；
  行尾 `\` 续行合并为单实例。
- **手动绘制流程**：cd virtuoso_ws && virtuoso → New Cellview(schematic) →
  I 放实例（tsmcN12 库 pcell symbol+参数）→ W 连线、L 命名内部 net → P 加 pin
  （按 subckt 端口序，VDD/VSS 用 inputOutput）→ X Check&Save → ADE 导 netlist
  与原 scs 逐项比对（实例数/节点/参数）。
- **下一步顺序**：① cmp_x GUI 收尾（6 pin+连线，顺带验证 GUI 流程）→
  ② gm_x/spd_x → ③ vco_x/vco_dual → ④ dtc_10b 画法决策（层级单元 dtc_unit vs
  Instance Array vs 仅 symbol 注明结构）→ VA 模块建 symbol。
- 本会话无新仿真/无代码改动：状态梳理 + 方案沉淀，原理图库 cellview 入库 git。

## 2026-08-31 存档：spd_x/cmp_x/gm_x 验证闭环 + tb 测试台 + 基准数据（本会话状态）

- **spd_x 验证闭环完成**：手绘原理图 si 导出 vs 参考 scs 全部一致。修复 2 处：
  RREF l=25u→**38u**（偏置电流差 1.52×）、内部偏置节点 net11→**VBSPD_M**（打 wire label 改名）。
  流程固化：桥读拓扑 → schCheck+dbSave → si 批量网表（si.env 需补 simViewList/simStopList，
  否则 stop-list/OSSHNL-109 报错）→ `tools/compare_block.py` 规范化比对（SI 后缀/
  16.0n≡16n/multi=(1)≡multi=1/忽略实例序）。
- **tb_spd_x 搭建+ADE 验证**（用户手绘）：CKDTC vpulse(6.5104n 周期/3.255n 宽/20p 沿) +
  vcvs 复位链（CKRSTI=−CKDTC、CKRST=CKRSTI+0.8，**E2.MINUS→VDC08 抬压**）+
  全部源负极 gnd!。V4 vpulse 曾漏设 v2/per/pw（CKDTC 恒 0、VRAMP 卡 358mV），修后波形
  与基准 <1% 一致。**基准数据**：斜率 214mV/ns、峰顶 677mV@3.255ns（20ps 边沿+开关阈值
  吃掉 ~40ps 窗口，非纸面 0.8V）、复位段 <1mV。CKFB 采样演示（delay=1.6n/w=0.5n）：
  VHOLD 阶梯收敛 424mV，采样窗口内斜坡斜率减半（CR0∥CH 电荷共享）。
- **cmp_x 验证闭环**：修复 5 处——7 管 fingers 1→**2**（参考 nf=2）、MP2 栅极接错
  （OUTP1→OUTN1，镜像非二极管）、MTAIL 衬底浮空→VSS、内部节点改名、标签桩交叉致
  OUTN1/OUTP1 短接（删线重建两网）。用户清理后 MP2.G 又接回 OUTP1、OUTN1 标签被删，
  各自修复后 si 比对全部一致。schCheck (0 0)。
- **gm_x 验证闭环**：修复 3 处——**MP2 l=16n→72n**（镜像 1/4.5）、3 个 NMOS 衬底浮空→VSS、
  net 改名 OUTN/TAILN。用户清理后 TAILN 标签被删（net9），补标签后一致。schCheck (0 0)。
- **tb_cmp_x/tb_gm_x 搭建**（tb_gm_x 由 tb_cmp_x Copy 改造，仅 EOUT→IOUT 之差）。
  tb_gm_x 已核验全对（7 实例/接线/gnd!）。比较器基准：失调 +0.7mV、过渡区 2mV、
  增益 347V/V、延迟 39.2ps、边沿 6.6ps（全部达标，判据见会话记录）。
  GM 基准（VREF=0.4/VI=0.55 钳位测流）：IOUT@0.4V=−1.59µA、**GM 阈值（零电流点）
  VINP=504.5mV**（LMS VREF DSM 要跟踪的点）、GM@阈值 ~27µS（论文 0.5µS 为复调目标，
  design.md TODO 未变）。
- **坑沉淀**：GUI 清理会顺手删网名标签→net 退化自动名（cmp_x/gm_x 各一次），清理后必须
  重新 si 比对；psfascii 解析 trace 名要精确匹配（Vl:p vs VI:p 混取会拿错电流）；
  Spectre `parameters` 语句在本机 20.1 无效（SPECTRE-16045），扫参用 `dc dev=Vi param=dc`。
- **工具链**（tools/）：compare_block.py（通用比对）、compare_spd_x.py、fix_cmp_x.py、
  rebuild_cmp_nets.py、fix_gm_x.py、read_spd_x.py、build_tb_spd_x.py + 各模块 si 导出网表
  + spd_x_sch_dump.json。基准目录 sim/tb_{spd,cmp,gm}_x_baseline/。
- **剩余**：vco_x（9 浮空节点保留、moscap_rf 三端 gate/bulk/gnode、cfmom nr=192）→
  vco_dual（Xb.VDD→VDDB）→ vco_dual_8g（复制改 1.5nH）→ dtc_unit+dtc_10b（桥批量
  1023 实例）→ VA×4 仅 symbol。

## 2026-08-31 晚：vco_x 验证闭环完成

- **vco_x 已转原理图并比对一致**（18 实例/5 端口/9 浮空节点全对，schCheck 0 18）。
  修复：① MN0/MN1 fingers/nf 1→16、CF0-11 nr 12→192（桥 dbReplaceProp 直改，已验证）；
  ② 用户手改 5 处接线：CF0/CF6 PLUS-MINUS 对调+shield 补 VSS、CF9 shield 补 VSS、
  CF7/CF8 的 net15/net16 对调；③ 修线时 CF1 被误删、补回后闭环。
- **坑沉淀**：simInitEnvWithArgs 在 run dir 已存在时弹对话框堵死 SKILL 通道（connect timeout，
  数十秒后自愈）→ 目录须先删且不要 mkdir 预创建；si.env 字段极少（6 行），si -batch 是独立
  shell 进程不走 SKILL 通道，手写 si.env + 补 simViewList/simStopList/simNetlistHier 即可导出；
  修线后必须重跑 si 比对（实例误删只在此处暴露）。
- 工具新增：tools/read_vco_x.py、export_vco_x.py、fix_vco_x.py、vco_x_sch_netlist.scs、
  vco_x_sch_dump.json。
- **剩余**：vco_dual（先给 vco_x 建 symbol，再放 Xa/Xb 两实例+4 开关管）→ vco_dual_8g（复制改
  1.5nH）→ dtc_unit+dtc_10b → VA×4 仅 symbol。

## 2026-09-01 存档：vco_x_8g 派生 + vco_dual_8g 检查修复闭环（本会话状态）

- **vco_x_8g 派生完成并验证**：`cp -r vco_x → vco_x_8g`（schematic+symbol，master.tag 只记
  oa 文件名、cell 名=目录名，直接拷安全），桥 dbReplaceProp 改 L0/L1 l=1.5n。桥读验证：
  MN0/MN1 nf=16、CF0-11 nr=192、CV wr=538n、9 浮空节点名/连接全对；schCheck 0 18（与 vco_x
  同口径，18 警告=9 浮空节点+符号方向提示，属预期）。
- **vco_dual_8g 绘制完成并修复 4 处**（拓扑 7 实例=2×vco_x_8g+5 管、4 内部网、6 pin）：
  ① 5 管 nf/fingers 全 1 → 桥修 MNEN/MPEN=2、MPWRB/MSWP/MSWN=64（读回验证）；
  ② MSWP/MSWN D/S 交叉接反（P 管接了 N 对）→ 用户 GUI 重接（D=核 A 侧 OUTP/OUTN、S=核 B 侧
  OUTPB/OUTNB）；
  ③ OUTP/OUTN pin 方向 input→output（否则 schCheck 报 "shorted output"×4）；
  ④ symbol 视图 OUTP/OUTN 方向同步 output（否则报 "Terminal in schematic is output but is
  input in symbol"×2，schematic 与 symbol 方向不一致）。
  另遇 "Pin name OUTN collides with net name OUTP"×2（pin 名与所接网名冲突），用户 GUI 修复后
  消失。**最终 schCheck (0 0)**，桥读拓扑与参考 netlist/inc/vco_dual_8g.scs 逐项一致
  （Xa/Xb 全端、EN2B/VDDB/OUTPB/OUTNB 网名、EN2 四栅连、VDD/VSS inputOutput 全对）。
- **si 闭环比对未跑**：si.env 已备好（/tmp/si_vco_dual_8g，补 simViewList/simStopList/
  simNetlistHier 共 9 行，cds.lib 已拷入），si -batch 被用户中断。下次续跑：cd 该目录跑
  `si -batch`，产物 netlist 与参考比对（X 实例 model 名 vco_x_8g→vco_x 需规范化，参考文件
  内联 vco_x subckt）。
- **schCheck 警告全谱速查**：floating net=预期浮空节点；shorted output=顶层 pin 方向应为
  output 却设 input；Terminal direction mismatch=schematic 与 symbol 方向未同步；pin name
  collides with net name=pin 实例接错网或与 wire label 冲突。
- **工具新增**：tools/read_vco_dual_8g.py（双 cell dump）、fix_vco_dual_8g.py（nf 桥修）、
  vco_dual_8g_sch_dump.json。桥 python 需 PYTHONPATH=virtuoso-bridge-lite/src + 其 .venv。
- **剩余模块清单（顶层手绘前置）**：① vco_dual（6.2G 版，与 vco_dual_8g 同构，Xa/Xb 换 2.49n
  的 vco_x cell，5 管/网名/pin 照抄，半小时级）；② dtc_10b（大头：R0+CKXB 反相器+MRST_D+
  1023×(开关 nf=2+CLSB 0.5fF)，1027 端口，需单独 dtc_unit 批量方案）；③ VA×5 仅 symbol
  （pll_mmd_edge 8 口 / pll_clk_lms 2 口·定义在 pll_hybrid_aux.va / pll_lms 11 口 /
  pll_dtc_decoder_10b 1027 口 / pll_doubler_edge 2 口·仅 tb 用）；顶层 PLL 原理图由用户手绘
  （例化清单见 scripts/gen_top.py，VA 网表需 ahdl_include 行补齐）。

## 2026-09-01 下午：dtc_10b + 顶层两层原理图全部闭环（本会话状态）

- **方案 A'（用户决策）**：解码器 Xdec 内嵌进 dtc_10b（论文架构），顶层 1023 条 c 网消失。
  - `netlist/inc/dtc_10b.scs` 重生成（11 端口 + Xdec 内嵌 + CODE→c 改名 + vth=0.5 显式，tools/gen_dtc_ref.py）
  - `gen_top.py`：删 Xdec 块、Xdtc 收为 11 口；`sim/pll_step2_main.scs` 重新生成
- **dtc_10b 原理图桥批量建成**（tools/build_dtc_10b.py 生成 .il + load_il，2053 实例）：
  标签命名法零手绘、33×31 网格、schCheck (0 0)、si 导出与参考**逐项一致**
- **VA symbol 建立流程变更**：Verilog-A import 本机不可用（缺 AMS 环境：xmvlog 纯 Verilog 模式
  解析不了标准 disciplines.vams）→ veriloga cellview 粘贴 + 编辑器 Create Symbol
- **si pin 排序规律实测**：实例行按字母序（VA 实例按 module 声明序，DB terminals 乱序无妨）；
  子电路头按 schematic pin 创建序；层级边界两侧不一致会端口错位（adpll_top OUTP/OUTN 曾交换，
  删 pin 按字母序重建修复）
- **adpll_top + tb_adpll_top 建成并闭环**：桥验证 21 实例/11 pin/接线逐位正确；桥修 Vref v1=0、
  buffer 管 nf=4、Xci ic=0.55、Xmmd.err_out 改接悬空网 ERR（参考如此）
- **si 平铺比对 30/30 全部一致**（tools/compare_tb_top.py：内联 subckt、丢 Xpll、节点集合比、
  type/edgetype/delay/seed/vth 白名单、canon 大小写不敏感）
- 新坑沉淀：嵌套 let 被桥包装器重写（用单层 let 双绑定）；~>props 槽对 VA/vdc 实例 nil（以
  dbFindProp 为准）；prop 更新用 if(存在→replace, 缺失→create)；改完必须 schCheck+dbSave（OSSHNL-109）；
  vpulse/isource CDF 字段名 v1/v2/per/pw/tr/tf（导出为 val0/val1/period/width/rise/fall）
- **剩余**：tb 导出网表补 4 行 ahdl_include 后即与 step2 仿真网表结构等价（可直接冒烟比对）
