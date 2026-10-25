# C 更新版：右上角网络信息 + LED 手电集成

> **当前版另已合并 TUMTaRA，速度数字和仪表盘恢复来源默认位置，共 222 个成员。** 当前安装、地图依赖和本轮回滚见 [C_TUMTARA_INTEGRATION.md](C_TUMTARA_INTEGRATION.md)。下文 221/76 成员、左上角速度表及旧回滚均属于历史阶段。

> **最新 C 已进一步集成 3230782214 的非准星 HUD 功能：血条、左上角速度表、计时器等。** 本次合并说明见 [C_HUD_INTEGRATION.md](C_HUD_INTEGRATION.md)。下文的 76 成员计数是 HUD 集成前记录，最新包为 221 个成员；本次回滚使用 `tools/rollback_hud.py`，下文的旧回滚工具仍保留用于更早版本。

## 当前安装文件

`dist/【00】C_ESC_LED_血条和速度_TUMTaRA.vpk`，后续成品继续使用此固定文件名，默认适配用户确认的 **1280×720 游戏渲染分辨率**。

退出游戏后将它复制到 `left4dead2/addons/`。只启用这个 C 版本，停用 A、B、旧 C 和独立 LED 手电模组，避免重复覆盖；`dist` 下的回滚副本和补丁重放副本不是额外依赖，不要一起安装。

原有 C 完整保存在 `originals/C_before_network_defaults.vpk`；旧工作源文件 `modified/` 未改，本次源文件在 `modified_c/`。

## 新默认项

| 设置 | 值 | 说明 |
|---|---:|---|
| 网络信息显示 | `net_graph 1` | 默认显示文本信息，而非额外的大型图形 |
| 水平位置 | `net_graphpos 1` | 右侧锚定，不写超大的自定义横坐标 |
| 高度 | `net_graphheight 620` | 720−100；高度是距底部的像素值，不是距顶部 |
| 网络图字体 | `net_graphproportionalfont 0` | 使用非比例字体，降低字体放大带来的越界风险 |
| 网络图文本 | `net_graphtext 1` | 保证文本开关打开 |
| 修复黑块 | `r_flashlightfov 200` | 该控件的原有最大值 |

展开的“网络图高度”和原网络下拉菜单的高度上限都改为 **620**，不再保留 720p 下可能移出屏幕的 2160 上限。

**“修复黑块”和“光射角”是同一个 `r_flashlightfov` 参数。** 不能把它们同时初始化为不同数值；按本次新要求统一默认 200，并将光射角滑条上限从 179 协调到 200，避免另一控件将值夹回去。是否产生预期画面、引擎是否接受 200 仍需游戏实测。

雾气关闭、尸体 0、两个轮廓参数为 0、光亮度 1、光射程 3000 等先前要求保留。

可在控制台明确应用全部 12 个指定参数：

```text
exec l4d2esc_defaults
```

固定范围初始化滑条沿用上一版机制，其构建/打开/重载触发时机、对后续手动调节的影响仍需实测。本次没有写入玩家已有配置或 autoexec。

## 分辨率适配：已实现的范围

ESC 菜单本身继续使用全屏尺寸、居中/右侧锚点，随分辨率缩放；网络图的 `net_graphheight` 不同，它是独立的像素参数。

**本次提供的是“按视频配置自动生成匹配的 C”，不是同一个 VPK 在运行中实时读取分辨率。** 没有把固定 620 冒充通用自适应；低于 720 高度时不要直接沿用此值。

在项目目录运行下面命令，会只读所指定的游戏 `video.txt`，读取 `setting.defaultres` / `setting.defaultresheight`，按 `net_graphheight = 游戏高度 - 100` 同步生成初始化值、两处滑条上限及 cfg，输出固定为 `dist/【00】C_ESC_LED_血条和速度_TUMTaRA.vpk`：

```text
python -X utf8 tools/build_c_mod.py --video "实际的游戏video.txt完整路径"
```

也可以明确提供渲染分辨率：

```text
python -X utf8 tools/build_c_mod.py --width 1280 --height 720
python -X utf8 tools/build_c_mod.py --width 1920 --height 1080
```

程序不自动覆盖游戏安装目录。重新生成后需要退出游戏、替换安装的 C 并重启。运行中改变分辨率或窗口尺寸，需要再次生成；无边框模式等情况下以游戏实际渲染尺寸为准，配置文件不一定反映即时窗口状态。

已测试 640×480、1280×720、1920×1080、2560×1440、3840×2160 的资源生成和有限坐标模型，分别使用高度 380、620、980、1340、2060。拒绝缺少尺寸字段的配置和无效尺寸，不会拿桌面尺寸冒充游戏窗口尺寸。

## LED 集成

指定的 [LED Flashlight (infected & survivor)](https://steamcommunity.com/sharedfiles/filedetails/?id=638169501) 已下载为 `originals/LED_638169501.vpk`，SHA-256：

`a605fdbc5b2c6594f6e6c5a933dfc43399b64cd22cf75586dffa60a44c1ef3ce`

其有效资源只有：

- `materials/effects/flashlight001.vtf`
- `materials/effects/flashlight001_infected.vtf`

两张纹理均已按原始字节集成进 C，原版作者为徒手开根号；保留其原包与说明文件在 `originals/` 和 `extracted/LED/`。依赖包的 `addoninfo.txt` 与 C 的同名描述文件冲突，因此保留 C 的描述，而不让依赖的说明覆盖菜单模组身份。没有其他脚本、菜单或着色器依赖。

## 验证与回滚

- C 原件：74 个成员；新 C：76 个成员。
- 原有资源仅修改 ESC 菜单、网络下拉菜单、指定默认 cfg；新增两张 LED 纹理，其他成员字节不变。
- LED 两张纹理逐字节匹配依赖原包；VPK 所有成员 CRC 通过。
- 补丁包：`reports/C_update_patch.zip`，包含清单、文本差异和五个变更/新增资源的完整载荷。
- 文本差异：`reports/C_update.patch`。
- 验证记录：`reports/C_verification.json`，保存确切命令、输入哈希、原样 stdout/stderr 和退出码。
- 补丁重放已执行，生成包与新 C 逐字节一致。
- 回滚工具：`python -X utf8 tools/rollback_c.py`，生成 `dist/C_before_update_restored.vpk`，已验证与上一版 C 完全一致。

回滚只生成项目内的恢复副本，不替换已安装的模组、不猜测玩家原来的 cvar。安装回滚副本时停用新 C；已经保存的个人参数需用自己的配置备份恢复。

**本次验证不是游戏运行验证。** 网络图坐标的风险判断参考 Valve 公开 [Source SDK 网络图实现](https://raw.githubusercontent.com/ValveSoftware/source-sdk-2013/master/src/game/client/vgui_netgraphpanel.cpp)；模型中保留顶部余量，但这不证明 L4D2 与该 SDK 分支完全一致。实际字体/文本宽度、ESC 初始化、在线参数限制及手电 FOV 200 的视觉效果仍待实测。
