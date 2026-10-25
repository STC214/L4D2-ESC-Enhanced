# A 布局参考 / B 功能保留修改方案

## 身份与证据

- A：3467154613，ESC Extended Menu Kokomi's Version (Adding ESC Flashlight)。
  SHA-256 `ac76f4baf11f7a944a3e9fcaa330cb1fbe9321e29bd99778b1a9df500afeb29c`。
- B：2906960647，ESC-Magnify flashlight。
  SHA-256 `dc6efecc83d1de19483ff46fbc964f1549d59852eb156599b21bc72d48f6108e`。
- 下载信息保存在 `originals/*.json`，文件来自 Steam 官方 UGC CDN。
- 原件只读使用；`extracted/A`、`extracted/B` 为逐项 CRC 校验后的解包副本。

## 观察

1. 两者 ESC 入口均为 `resource/ui/l4d360ui/ingamemainmenu.res`。
2. A 的根窗口及背景使用 `f0` 全屏尺寸；主按钮在左，190 单位宽的滑条按约 20 单位行距分栏。
3. B 入口同样全屏，但设置挤在右方 97 单位宽滑条与底部 13 单位行距区域，部分滑条高度仅 2。
4. B 的准星与网络参数在 `dropdowncrosshair.res`、`dropdownnetgraph.res`；雨雪在 `dropdownweathercontrol.res`。
5. B 的“光射角” `Flashlightfov` 为 `r_flashlightfov`，范围 100–179；“修改内扩” `GuangSheJiao` 也是同一 cvar，范围 50–200，并非两个独立设置。本次按“光射角”的明确上限 179 初始化，两个原调节范围均保留。
6. B 没有尸体数量控件，新增来自 A 同名功能的 `cl_ragdoll_maxcount` 控件，范围 0–75。
7. B 有重复 `ImgFOV` 装饰图标名称；保留原资源，仅隐藏旧位置装饰，改为直接文字标签。

## 实施方案

- 仅以 B 为打包基底，不把 A 的材质、相机参数或其他默认值移入 B。
- 三栏按左边距 / 屏幕中心 / 右边距锚定，根背景铺满；滑条文字与点击高度统一，避免旧 2 像素控件。
- 主操作保留在左；现有直接设置与展开的准星、网络、雨雪参数分布于另外两栏，尽量按 19 单位行距铺满 480 高的 VGUI 逻辑画布。
- 保留原下拉入口及资源用于帮助、兼容与分屏，不把投票、选项等游戏操作的动态子菜单强制常驻展开。
- 现有滑条的 conCommand / minValue / maxValue / stepSize 等非布局语义保持原样。
- 七项初始值通过末尾专用、屏幕外固定范围 SliderControl 初始化，参考 A 的屏幕外固定范围 fog_override 控件做法；可见控件仍保留调节能力。其触发时机取决于引擎构建/重载菜单，不承诺只初始化一次。
- 额外附带独立 `cfg/l4d2esc_defaults.cfg`，只设置这七项，可在控制台显式执行 `exec l4d2esc_defaults`，不覆盖 autoexec 或用户配置。

| 请求 | cvar | 初始值 |
|---|---|---:|
| 雾气开启保持关闭 | fog_enable | 0 |
| 尸体数量 | cl_ragdoll_maxcount | 0 |
| 角色轮廓最明显 | sv_disable_glow_survivors | 0 |
| 物品轮廓最明显 | sv_disable_glow_faritems | 0 |
| 光亮度最大 | r_flashlightconstant | 1 |
| 光射程最大 | r_flashlightfar | 3000 |
| 光射角最大 | r_flashlightfov | 179 |

## 验收边界

- 自动验证：VPK 文件身份、目录结构、全员 CRC、原资源保留、修改白名单、未指定参数范围不变、七项初始化资源、不同宽高比下静态矩形边界与重叠检查。
- 游戏运行验证仍需在 L4D2 中确认：字体和引擎内部子控件实际尺寸、滑条初始化是否触发、服务器 cvar 限制、ESC 重开、下拉菜单、投票与不同模式按钮。
- 不修改 sv_cheats、游戏 DLL、服务器策略或玩家已有配置。部分 B 自带服务端/受限 cvar 在不同服务器上的执行结果由引擎决定。
- 本项目未发现游戏安装或可运行测试场景，因此静态通过不写成游戏实测通过。

## C 后续更新：网络图与 LED 集成

- 用户将前次产物命名为 C，并确认实际渲染分辨率为 1280×720。原 C 已按 SHA-256 `ba3f39a3115e9cda4bf32213277095de52435198e41c6dc55d18f0eadd6797bf` 保存到 `originals/C_before_network_defaults.vpk`。
- 用户当前称“修复黑域”的选项对应资源中的“修复黑块” `GuangSheJiao`，其上限为 200，仍共用 `r_flashlightfov`。本次新要求覆盖上文历史方案中的默认 179；可见光射角控件上限同步为 200，避免夹回 179。
- 右上角文本默认参数为 `net_graph 1`、`net_graphpos 1`、`net_graphheight 620`、`net_graphproportionalfont 0`、`net_graphtext 1`。两个高度滑条的上限同步为 620。
- 参考 Valve 官方 Source SDK 的 `GraphGetXY` / `DrawTextFields` / `ComputeNetgraphHeight`：右侧可以使用语义锚点，高度影响从底部到文本的偏移。按该分支的有限模型，H−100 留出顶部余量。该推断不充当 L4D2 运行观察。
- 分辨率方案是打包时自动读取视频配置并生成匹配资源，而非纯 VPK 实时自适应。当前没有发现可在既有 RES 入口中直接读取窗口高度并写入该像素 cvar 的机制；没有引入 DLL 注入、服务器脚本或宣称实时切换已经实现。
- 必备 LED 条目 638169501 已下载，SHA-256 `a605fdbc5b2c6594f6e6c5a933dfc43399b64cd22cf75586dffa60a44c1ef3ce`。两张 `materials/effects/flashlight001*.vtf` 与 C 资源路径不冲突，已逐字节集成；依赖的 `addoninfo.txt` 不覆盖 C 同名描述。
- 新 C 保留原来 74 个成员，修改 3 个文本资源，新增 2 张纹理，共 76 个成员。`modified_c/` 是本次工作副本，`modified/` 与旧版产物均保留。
- 720p、1080p、1440p、2160p 和 480p 生成、越界高度负例、补丁完整重放及恢复旧 C 均已自动验证；见 `reports/C_verification.json`。仍未进行 L4D2 游戏实测。
- 完整安装、自动生成命令与回滚说明见 [C_README.md](C_README.md)。

## C 后续更新：HUD 3230782214（不含其准星）

- 前一条请求中的 `cl_showpos` 实现尚未打包，随后用户选定带速度表的 HUD。本次采用已观察到的 `PlayerSpeed` 材质代理，撤回本轮尚未交付的诊断显示初始化，避免额外坐标/视角叠加；不是撤销用户原有内容。
- 下载、源包哈希、准星剔除位置、速度表左上角平移、同名材质隔离、倒地队友血条原始多余括号修复与覆盖边界详见 [C_HUD_INTEGRATION.md](C_HUD_INTEGRATION.md)。
- 当前 720p 配置下保留之前 C 的全部 76 个成员原字节，新增来源 HUD 的 145 个运行资源，合并后 221 个成员。
- 观察到：血条由原生 HealthPanel 读取血量，速度指针和数字材质由 PlayerSpeed 绑定。未知：实际游戏中这些原生入口的加载、刷新以及不同模式行为。本次不把静态检查写成游戏实测。

## 后续全量审核修复

- 用户要求重复全量审核与修复。新增独立 KeyValues 审核、VTF 帧/mipmap 边界审核、材质代理有限模型和 20 项回归/故障注入测试，发现并修复旧检查遗漏的原包缺陷。
- 当前速度数字不再保持来源原字节：四位取位逻辑修正为受限整数帧，解决 85→0080 等模型反例。
- 相对 HUD 集成前的 76 个成员，75 个继续逐字节保留，仅 ESC 菜单一个重复 fieldName 被修正；其他修复位于导入的 HUD 资源及构建/验证工具。
- 已从头重建并完成连续两轮全量静态/回归复审，均零错误、20 项测试全过、产物哈希一致。完整问题表与未覆盖项见 [FULL_AUDIT_REPORT.md](FULL_AUDIT_REPORT.md)。

## 后续 TUMTaRA 合并与来源速度布局恢复

- 从上次已审核 C（`5eb9113d...`）局部合并 2256147202 的五个入口/弹出控件，保留 C 的整个工具箱与原主菜单控件，仅增加三个右向导航字段。
- 按钮包本身没有地图菜单；另下载官方依赖 469986973（原始 SHA-256 `d23e5738e0258896f91ef05425b671b107f06d67bf50a49eb6353c18985a0e32`），只导入其真实启动菜单，不把地图/脚本合入通用 ESC 包。游戏安装仍需主地图依赖及用户要使用的额外地图。
- 速度相关父面板恢复 y=180，整个 pickup 子资源恢复来源字节；四位速度计算修复保留，准星排除与既有血条修复保留。
- 新包只变化三个既有文本成员，新增一个菜单资源；其余 218 个成员逐字节相同。新增六项针对性测试，共 26 项；本轮补丁、验证、回滚说明见 [C_TUMTARA_INTEGRATION.md](C_TUMTARA_INTEGRATION.md)。

## 固定成品文件名与再次全量复审

- 后续 C 成品固定为 `dist/【00】C_ESC_LED_血条和速度_TUMTaRA.vpk`，由 `tools/release_paths.py` 集中定义；构建、审核、速度模型、合并验收与两轮审查统一使用此路径。
- 本轮前成品保存到 `originals/C_before_fixed_filename.vpk`，旧名称副本保留在 `dist/history/`；新名成品与原包全部字节相同，不改既有功能。
- 新增四项测试，共 30 项。故障注入确认旧 TUMTaRA 验证器漏检按钮越界、弹窗偏移异常与控制台命令损坏；现已增加完整新增字段核对与基于实际字段的坐标计算，三个反例均被拒绝。
- 本次名称恢复工具为 `tools/rollback_release_name.py`，只在项目子目录生成旧名称恢复包。全量复审记录仍为 `reports/full_review_verification.json`；游戏运行证据与未覆盖项继续如实单列。
