# fbank 单元切换 glitch 测量（2026-09-14，本机 spectre 20.1，tt 12nm）

## TB（sim/vco_glitch_tb2.scs + sim/glitch_dut.scs）

- DUT：vco_x_c_dac LC 核（8.034GHz，验证可靠起振）+ 一对 EN 开关切换的差分变容管单元
  （moscap_rf nfin=NFIN_U + ulvt 开关 nf=NF_SW，cb→VSW；EN=0.8 切入 / 0 切出）
- 协议：EN 在 t=TSW 切入、WON(5n=40 周期)后切出；三窗相位拟合 t_k=a+b·k，
  边界拟合截距差 = kick；ON 段短使设计步进被中窗斜率吸收、kick 与设计步进分离
- 数值：maxstep=1p + errpreset=moderate（rms≈5fs；liberal/2p 基频偏 28MHz 不可用）
- 提取脚本：glitch_matrix.py（矩阵编排+提取）；结果 glitch_results.txt

## 结果（全部 1p/moderate）

| tag | step(MHz) | kick_on(fs) | kick_off(fs) | net(fs) | fs/MHz | 备注 |
|---|---|---|---|---|---|---|
| conv | 44.18 | −4032 | +3992 | **−40** | 91.3 | 基准(50p边沿) |
| m_conv2 | 44.18 | −4032 | +3975 | −57 | 91.3 | WON 3n,窗口无关性✓ |
| m_ph3/6 | 44.17-8 | −3713/−4095 | +4407/+4113 | +694/+18 | 84-93 | 相位依赖弱(±5%) |
| m_sz4/8 | 42.3-42.7 | −3847.. | +3786.. | −61 | 90.9 | **步进被开关RC主导,变容管加大无效** |
| m_sw4 | 62.32 | −5741 | +5707 | −34 | 92.1 | 开关×2→步进×1.41→kick∝步进 |
| m_vsw20/40 | 60.7 / 23.9 | −5546 / −2193 | +5499/+2135 | −47/−58 | 91.3/91.8 | 步进24-62MHz全落91fs/MHz |
| m_half | 44.18 | −4032 | +3813 | −219 | 91.3 | ON/OFF相位差大→残差5% |
| m_tr200 | 44.18 | −3257 | +4366 | **+1109** | 73.7 | 200p慢边沿→抵消崩坏(27%) |

## 三条结论

1. **台阶型，非振铃**：切换后 1 个周期过冲，随即周期精确落在新设计值
   （44.18MHz→+676fs/周期 ✓），相位偏移持久保持——alg0914 模型的"永久相位台阶"
   假设被证实。
2. **on/off 高度对称**：50ps 快边沿下 net 残差 1–1.5%（−34~−61fs vs ±4ps kick），
   即使两次切换相位组合不同仍抵消；**慢边沿(200p)使抵取消坏到 27%**——
   保持快边沿是硬要求。模型 randn 独立假设（每次 kick 独立零均值）过于悲观 ~70×。
3. **标度律：kick ≈ 91±1 fs / MHz(设计步进)**，跨步进 24–62MHz、开关尺寸、
   偏压、相位不变（电荷注入∝有效切换电容）。

## 对 alg0914 模型的换算（关键）

- 91fs/MHz × 单元步进：
  - **alg0914 fbank 单元(7.34kHz) → 0.67fs/切换**（模型假设 100fs/code 悲观 ~150×）
  - 1bit 单元(58.7kHz) → 5.3fs
  - **12nm 物理离散电容单元(0.5-0.7fF≈5-10MHz，cf. dco-12nm-cap-floor) → 0.5–0.9ps/切换！**
- 推论：**细bank 不能用物理离散电容做**（每切一次踢 0.5-0.9ps，模型等效
  fs/code≈91×Δf(MHz)，jitter 会到 ~10ps 级）；细路径必须 DAC+变容管连续调
  （无切换事件）——ref3 三bank+DAC 方向获得定量依据。
  若算法侧保持 7.34kHz 等效单元（插值/连续实现），glitch 项塌缩到 ~10fs 级，
  1421fs 的主宰项消失。
- 局限：理想电源/无衬底耦合/无版图寄生——91fs/MHz 是该拓扑的**乐观下限**
  （仅本地电荷注入通道）；tt corner；moscap_rf 模型。

## 文件

- vco_glitch_tb2.scs / glitch_dut.scs（参数化 NFIN_U/NF_SW/TSW/WON/TRISE）
- glitch_matrix.py（13+9 变体矩阵）；tbx_*.scs / gs_*/（各 run）
- glitch_results.txt（liberal 批，已弃用）+ 本文件（1p/moderate 权威数据）
