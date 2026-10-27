# C 全量审核与修复结果

> **历史归档，不是当前安装教程。** 原路径：`FULL_AUDIT_REPORT.md`。文中的“当前/最新/本轮”均指当时阶段；旧默认值、布局、哈希和回退命令不代表 C 1.3.1。当前使用见 [C 使用说明](../C使用说明.md)，完整分类见 [文档索引](../INDEX.md)。代码块与反引号中的项目路径仍按项目根目录解释；部分历史试验包/恢复副本已清理，原始输入与核心审查证据保留。


> **当前固定命名版**：`dist/【00】C_ESC_LED_血条和速度_TUMTaRA.vpk`，222 成员、142 个 KeyValues、79 个纹理、30 项回归测试；本轮改动和验收边界见 [C_TUMTARA_INTEGRATION.md](C_TUMTARA_INTEGRATION.md)，两轮原样记录见 `reports/full_review_verification.json`。最新 SHA-256 为 `97fa1e054d0676042b9da149b421e645aad493160db98b7f04668a2503e463da`，本轮回滚为 `tools/rollback_release_name.py`。

本次复审修复的是审核器的三个漏报：新按钮位置、弹窗偏移、控制台命令损坏；故障注入从失败转为通过。没有为了让审核通过而删改游戏功能，成品 222 个成员及归档字节均与上次合并版相同。构建、审查、速度模型与合并验收均统一使用固定输出路径；历史冲突诊断改为读取其原始备份，避免误读最新 C。

以下保留首次全量修复的历史过程；其中 221 成员和 20 项测试不是最新计数。

## 本轮结论

已执行“发现问题 → 最小修复 → 针对性验证 → 重打包 → 完整复审”循环。
最后从头重建并完整检查两轮，两轮结果均为：

- 221 个 VPK 成员 CRC 与结构检查通过。
- 141 个 KeyValues 资源完整解析通过，不只检查大括号数量。
- 79 个 VTF 纹理的头部、帧、mipmap 数据边界检查通过。
- 20 项回归/故障注入测试全部通过，含五种分辨率。
- 补丁重放和本轮回滚执行通过。
- 两次独立重建的 VPK 字节完全一致。

该历史审核版：`originals/C_before_tumtara_merge.vpk`

SHA-256：`5eb9113d019b750f00827128bbfb1bcd331feae7e05e23a8dcfa036270a06e0e`

**这是已具备环境内的全量静态与模型/回归审核结论，不是“游戏运行完全无问题”的保证。**

## 发现并修复的问题

| 位置/类别 | 发现 | 处理 |
|---|---|---|
| `active.vmt`、`scalablepanel_bgblack_outlinegrey.vmt` | 缺少 Proxies 和根对象结束括号 | 补齐结束括号，完整解析回归 |
| `arcgpt.vmt` | 根对象结束后残留无值的 `ArcPav` | 去掉孤立尾标记，保留材质代理 |
| `s_equip_bg_inactive.vmt` | 两个不同 `$baseTexture`，后一个引用不存在的本地贴图 | 保留包内确实存在的纹理引用 |
| `healthbar_bg_player.vmt` | 引用 `healthbar_bg_4` 而包内提供的是 `healthbar_bg_player.vtf` | 指向对应的自带玩家血条贴图 |
| 本人/队友倒地面板 `DownSign` | `fieldName` 错写成 `Head`，和头像冲突 | 统一为 `DownSign`，不改血量绑定 |
| `teammatepanel.res` | 两个同名 `Head` 控件，几何不同 | 保留后声明的 30×30 头像，消除重复实例 |
| ESC 第三人称左偏移滑条 | 与高度滑条共用同一个 `fieldName` | 对齐自身块名 `c_thirdpersonshoulderheight-`，保留参数与范围 |
| 当前速度数字 | 个位取值错误；模型中 85→0080、1205→1201；小数边界和超范围帧也异常 | 四位数字统一使用明确浮点中间量和整数帧，速度取非负整数，显示范围 0000–9999 |
| 视频配置读取 | 原正则可能读入注释或静默采用重复字段 | 改用完整 KeyValues 解析，拒绝不完整、重复和非整数尺寸 |
| 构建 CLI | `--width 0` 会误退回默认尺寸 | 明确区分 0 与未提供参数；无效尺寸不发布产物 |
| 文本差异 | 新文件的源路径没有标为 `/dev/null` | 改成标准新增文件头；完整补丁包仍校验全部载荷 |
| HUD 验证 CLI | 只能按默认 720p 核验 | 增加明确的宽高参数 |
| 审核方法 | 旧验证较多依赖与生成器同源的期望输出，漏掉原包继承缺陷 | 增加独立解析器、纹理边界检查、有限代理模型和故障注入测试；构建前先执行独立审查门禁 |

初筛中计分板 `BackgroundImage` 的重复声明经核对属于互斥的 Xbox/Windows 分支，是误报。已修正审核器的平台条件处理，没有误删这两个分支。

## 速度模型的证据与限制

保留来源模组的 `PlayerSpeed` 数据入口和速度表美术。当前速度数字修正使用公开 Source SDK 的浮点/整数材质代理语义构建有限模型，覆盖首次绑定、连续绑定、整数、小数边界和范围饱和测试。

参考源代码：[材质数学代理](https://raw.githubusercontent.com/ValveSoftware/source-sdk-2013/master/src/game/client/mathproxy.cpp)、[代理结果类型](https://raw.githubusercontent.com/ValveSoftware/source-sdk-2013/master/src/game/client/functionproxy.cpp)、[玩家速度代理](https://raw.githubusercontent.com/ValveSoftware/source-sdk-2013/master/src/game/client/proxyplayer.cpp)。模型并不证明 L4D2 分支与公开 SDK 完全相同。

最大/平均速度原代理链保留，在有限输入序列下验证最大值和非零采样平均值。真实引擎中的绑定频率、观战对象、地图切换和复位仍需游戏实测。

## 保留与回滚

- 所有下载原件不变。
- 审核前 C 备份：`originals/C_before_full_audit.vpk`，SHA-256 `75cf4ab83a8656587799555f1678b210c6300f586a1d243cd08e2d76b06256c3`。
- C 的准星、LED、菜单布局、指定 12 项默认值保留；未改移动速度参数。
- 相对 HUD 集成前的 76 个成员，当前仅 ESC 菜单的一个重复控件标识因审核而变化，其余 75 个成员字节不变。
- 最新补丁：`reports/C_update_patch.zip`，文本差异：`reports/C_update.patch`。
- 本轮回滚：`python -X utf8 tools/rollback_audit.py`，生成 `dist/C_before_audit_restored.vpk`，已执行并验证与审核前 C 完全一致。
- 回滚不更改游戏安装或个人配置。更早的回滚脚本仍保留，各自恢复对应历史版本。

## 两轮完整复审记录

执行入口：

```text
python -X utf8 tools/full_review.py
```

- 完整命令、原样 stdout/stderr、退出码、代码与产物哈希：`reports/full_review_verification.json`。
- 审核前问题复现：`reports/full_audit_baseline.json`。此项预期退出码为 1，以证明审核器确实发现旧包问题。
- 最后两轮独立审核：`reports/full_audit_clean_1.json`、`reports/full_audit_clean_2.json`，均为 0 错误。
- 构建/补丁/历史回滚记录：`reports/C_verification.json`。

## 尚未覆盖的项目

1. 有 27 处资源引用依赖基础游戏文件，项目没有这些基础资源用于逐项核对。清单保存在独立审核 JSON 中，没有把它们伪装成已经验证的依赖。
2. 尚未启动 L4D2，未实测 HUD 加载、血量动画、实时速度刷新、实际字体边界、分屏和不同模式。
3. ESC 默认初始化、手动调节、在线 cvar 限制与 FOV 200 的视觉效果仍需实际游戏验证。

这些属于缺少游戏运行环境的验证缺口，不计为本轮已修复或已证明不存在的问题。
