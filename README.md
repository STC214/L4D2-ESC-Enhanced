# B 全屏 ESC 菜单修改版

> **聊天位置更新：** C 的聊天历史与输入行统一移至右下方，保留底部 HUD 空间；构建、审核、实际部署记录与回滚见 [聊天布局说明](C_CHAT_BOTTOM_RIGHT.md)。

> **当前 C：重复选项已合并，天气默认关闭，每张地图首次 ESC 将“手电光圈”设为 150，之后不锁定。** 使用 1.1.0 配套 DLL；成品、构建、审查与回滚见 [本轮说明](C_MENU_CONSOLIDATION.md)。下方旧版默认值与审核记录保留作历史参考。

> **本机状态：Evolved 已按要求从游戏目录清理，L4N 与 C 保留。** 30 个文件的备份、核验和恢复入口见 [Evolved 清理记录](docs/Evolved清理记录.md)。旧 Evolved 部署说明仅为历史记录，不表示当前仍安装。

> **平台来源与共存检查：** [三个工坊页面、VPK 下载逻辑及 Skeeto/Evolved 功能冲突清单](docs/平台来源与功能冲突清单.md)。以 L4N 为基底，保留现有设置；机器可读来源为 `docs/workshop-platforms.json`。本轮仅静态检查，没有安装 Skeeto 或更新 L4N。

> **最新 C 会话默认项修正：** 移除每次 ESC 的初始化控件，黑块修复/光射角恢复原生默认 53；自动入房初始化改由配套 L4N 组件承担。安装两件套、回滚与游戏内待验证项见 [C_SESSION_DEFAULTS.md](C_SESSION_DEFAULTS.md)。EXE 更新检测、下载和选项接口规范已补充至设计文档第 12 节；EXE 本体尚未实现。

> **最新 C：已合并 TUMTaRA 主菜单入口与真实地图菜单，速度数字/仪表盘恢复来源默认位置。** 安装、地图依赖、补丁和本轮回滚见 [C_TUMTARA_INTEGRATION.md](C_TUMTARA_INTEGRATION.md)。最新包为 222 个成员；下文及旧说明中的左上角速度布局与旧回滚属于历史版本。

> **C 的成品文件名今后固定为 `dist/【00】C_ESC_LED_血条和速度_TUMTaRA.vpk`。** 构建、审核和验证统一读取 `tools/release_paths.py`，不再发布旧文件名；旧包保留在 `dist/history/`，不要与新包一起安装。
> 请先阅读 [C 更新版说明](C_README.md)。下面保留上一版的历史记录；其中的 179 上限和未合并 LED 的描述不适用于最新 C。旧脚本 `tools/build_mod.py` 仍复现旧版，新 C 使用 `tools/build_c_mod.py`。
> HUD 集成历史与当前布局说明：[血条、速度表和其他 HUD 功能，排除来源准星](C_HUD_INTEGRATION.md)。
> 全量审核修复记录：[FULL_AUDIT_REPORT.md](FULL_AUDIT_REPORT.md)。本轮文件名变更回滚工具为 `tools/rollback_release_name.py`；`tools/rollback_tumtara.py` 仍用于回退上次 TUMTaRA 合并。

## 文件

- Evo 小地图位置、比例尺寸、四角示例与恢复步骤：[小地图位置与尺寸设置](docs/L4D2Evolved_小地图位置与尺寸设置.md)。

- 后续自动化 EXE 的检查、适配与恢复逻辑：[实现规范](docs/L4D2Evolved_自动适配流程与EXE实现规范.md)；配套[版本化规则数据](docs/evolved-adaptation-rules.v1.json)。当前为设计资料，尚未实现安装器。

- 原版 A：`originals/A_3467154613.vpk`
- 原版 B：`originals/B_2906960647.vpk`
- 修改版：`dist/B_fullscreen_esc.vpk`
- 分析与修改方案：`ANALYSIS.md`
- 完整文本补丁：`reports/B_fullscreen.patch`
- 命令、原样输出、退出码及输入哈希：`reports/verification.json`
- 回滚工具：`tools/rollback.py`
- 已验证的原版恢复副本：`dist/B_original_restored.vpk`

## 安装

1. 退出游戏，将 `dist/B_fullscreen_esc.vpk` 复制到游戏的 `left4dead2/addons/`。
2. 在游戏的附加内容里仅启用这个 ESC 菜单版本；停用原版 A、原版 B 以及覆盖同一 ESC 菜单的其他模组，避免资源冲突。不要把 `dist` 中的两个 VPK 一起装入。
3. 保留原版 B 所需的其他依赖；本次没有额外下载或合并依赖模组。
4. 重新启动游戏、进入地图后按 ESC，检查三栏布局。

未向实际游戏目录写入任何文件，也未改玩家的 autoexec、config 或 Steam 订阅状态。

## 指定初始值

| 设置 | 值 |
|---|---:|
| 雾气开启 | 0 / 关闭 |
| 尸体数量 | 0 |
| 角色轮廓、物品轮廓 | 都为 0，即各自滑条最小值 |
| 光亮度 | 1 |
| 光射程 | 3000 |
| 光射角 | 179 |

光射角采用 B 原来“光射角”控件的上限 179，而非 A 的光射程上限 6000，也非 B 中另一个共用同一参数的“修改内扩”控件上限 200。B 中未指定的参数及原有滑条范围保持原样。

初始化参考 A 使用固定范围滑条的机制，初始化控件排在文件末尾、位于屏幕外。**尚未进行游戏内验证**：这些控件是否在首次打开、再次打开或重载菜单时触发，是否影响随后手动调节，仍需实测；不要把它理解成已验证的“一次性写入默认值”。

VPK 内另有只包含七项设置的独立配置。需要明确应用时，在游戏控制台运行：

```text
exec l4d2esc_defaults
```

它不自动加载、不修改 `sv_cheats`、不包含其他设置。受服务端或引擎限制的 cvar 以控制台实际反馈为准；静态检测不代表在线服务器一定接受这些值。

## 已完成验证

- 两个官方原件的 SHA-256、VPK 目录和全部成员 CRC。
- 修改版 74 个成员，其中 B 原有 73 个资源全部保留，只有 `ingamemainmenu.res` 内容变化，新增一个独立 cfg。
- 48 个设置滑条、17 个操作/下拉入口，在 4:3、16:10、16:9、21:9、48:9 下的静态矩形边界和互不重叠检查。
- 现有滑条参数、调节范围、步长与直接操作按钮命令保持不变。
- 七项初始化资源值与 cfg 指令一致。
- 保存的 unified diff 重放后与修改版所有成员完全一致。
- 回滚工具运行成功，恢复副本与原版 B 的 SHA-256 完全一致。

静态矩形不包含引擎动态子控件、弹出菜单或字体实际渲染。仍需游戏内检查 ESC 重开、拖动滑条、投票/设置弹出菜单、不同游戏模式和服务器限制。

## 复现与回滚

在本项目目录执行：

```text
python -X utf8 tools/build_mod.py
python -X utf8 tools/verify_menu.py dist/B_fullscreen_esc.vpk --modified
python -X utf8 tools/build_mod.py --verify-patch
python -X utf8 tools/rollback.py
```

回滚命令只在项目 `dist/B_original_restored.vpk` 生成/核验原版，不操作游戏安装目录。要恢复已安装的模组：退出游戏，停用修改版，并只启用原版 B 或将恢复副本作为唯一 ESC 菜单模组安装。

恢复 VPK 不会自动还原游戏已经写入个人配置的 cvar。安装前备份自己的游戏配置，必要时用自己的备份恢复；这里不猜测未提供的旧参数值。
