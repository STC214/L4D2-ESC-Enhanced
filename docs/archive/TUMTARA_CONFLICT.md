# 2256147202 与 C 的冲突检查

> **历史归档，不是当前安装教程。** 原路径：`TUMTARA_CONFLICT.md`。文中的“当前/最新/本轮”均指当时阶段；旧默认值、布局、哈希和回退命令不代表 C 1.3.1。当前使用见 [C 使用说明](../C使用说明.md)，完整分类见 [文档索引](../INDEX.md)。代码块与反引号中的项目路径仍按项目根目录解释；部分历史试验包/恢复副本已清理，原始输入与核心审查证据保留。


> **后续已按用户要求完成局部合并**：入口和真实地图菜单加入 C，原工具箱保留，速度表恢复来源默认位置。当前说明见 [C_TUMTARA_INTEGRATION.md](C_TUMTARA_INTEGRATION.md)。下文是修改前的只读检查记录，221 成员哈希对应 `originals/C_before_tumtara_merge.vpk`；依赖主包在后续合并时已另行下载检查。

## 结论

**已确认直接资源冲突。首要冲突是主菜单整文件 `resource/ui/l4d360ui/mainmenu.res`；另有 `extrasflyout.res` 冲突。**

若游戏在同名路径上优先读取 C，TUMTaRA 模组新增的主菜单按钮和菜单入口就不在实际使用的资源里，足以解释“主菜单没有生效”。这不是 C 的血条、速度表或 LED 材质冲突，而是 C 保留的 B 版主菜单资源与它争用同一路径。

此结论是两份实际 VPK 的静态比较与文件优先级模型，不代表已经读取用户游戏的实际加载顺序。安装的版本、真实优先级和其他模组均未检查。

## 范围与身份

只检查 C 与指定的 [TUMTaRA Main Menu Buttons](https://steamcommunity.com/sharedfiles/filedetails/?id=2256147202)。未下载/检查它的依赖主包，未检查其他已安装模组，未修改任何 VPK 或游戏文件。

| 文件 | 成员数 | SHA-256 |
|---|---:|---|
| `originals/C_before_tumtara_merge.vpk`（当时的 C，旧名 `C_fullscreen_esc.vpk`） | 221 | `5eb9113d019b750f00827128bbfb1bcd331feae7e05e23a8dcfa036270a06e0e` |
| `originals/TUMTARA_2256147202.vpk` | 4 | `023174c1784458a15489b985d621073361d959258566fce2f4d2ceb81b9fdf40` |

两包成员 CRC 均验证通过；检查结束后再次核对，输入 VPK 哈希未变。

## 具体冲突点

### 1. 主菜单入口被覆盖

双方均提供：

```text
resource/ui/l4d360ui/mainmenu.res
```

TUMTaRA 模组在这里包含以下控件；C 的同一文件均没有这些控件：

| TUMTaRA 文件位置 | 控件 | 功能/引用 |
|---|---|---|
| 第 26 行 | `BtnTUMTaRA` | `command = FLMTumtara` |
| 第 87 行 | `FlmTUMTaRA` | `ResourceFile = resource/ui/l4d360ui/more/FlmTUMTaRA.res` |
| 第 46 行 | `BtnConsole` | `command = #toggleconsole` |
| 第 66 行 | `Btnserverbrowser` | `command = OpenServerBrowser` |
| 第 4 行 | `RELOAD_UI` | 重载 UI 按钮 |

同名资源文件的选择不会把两个模组的新增控件自动拼接在一起。按单文件优先读取模型：

- **C 的文件获选：** 使用 C 的主菜单；TUMTaRA、控制台及主菜单服务器浏览器按钮不出现。
- **TUMTaRA 的文件获选：** 按钮定义出现，但 C 在同一主菜单文件中的布局、中文标签等定制被替换。

参考公开 Source SDK 的 [KeyValues 文件加载](https://raw.githubusercontent.com/ValveSoftware/source-sdk-2013/master/src/tier1/KeyValues.cpp) 与 [VGUI 面板资源入口](https://raw.githubusercontent.com/ValveSoftware/source-sdk-2013/master/src/vgui2/vgui_controls/EditablePanel.cpp)。本次没有用文件名或订阅顺序推测用户实际加载优先级。

### 2. “工具箱/Extras”菜单也争用同一路径

双方均提供：

```text
resource/ui/l4d360ui/extrasflyout.res
```

- C：录像播放、音频缓存工具、配置重载、服务器浏览器等扩展入口。
- TUMTaRA：开发者解说、制作人员、博客入口及较小的菜单背景。

两份内容不同，因此切换谁优先会造成另一方在该文件中的菜单配置丢失。C 的服务器浏览器仍可能出现在“工具箱”中，这不意味着 TUMTaRA 新增的主菜单按钮已经加载。

### 3. 同名元数据不是主要功能冲突

两包还有 `addoninfo.txt` 同名且内容不同；这是附加内容说明信息，不是 TUMTaRA 主菜单入口丢失的主要证据。

这两个运行时 UI 文件在 C 中与其 B 来源包的对应文件逐字节一致，已核对来源。这里仅用于追踪 C 内部文件来源，没有额外排查 B 或其他已安装模组的运行状态。

## 仅记录、不扩展排查的依赖边界

TUMTaRA 按钮引用的：

```text
resource/ui/l4d360ui/more/FlmTUMTaRA.res
```

在 C 与这个按钮 VPK 中都不存在。作者说明也明确此模组只提供入口，真正的地图菜单随 TUMTaRA 主文件提供。

因此须区分：

- **按钮本身不出现：** 本次已确认的 `mainmenu.res` 冲突是直接解释路径。
- **按钮出现但点不开地图菜单：** 应再检查上述菜单资源和依赖主包；按用户要求，本轮没有检查，也没有认定依赖缺失。

## 后续兼容修复方向（本轮未执行）

要同时保留功能，应以 C 的主菜单为基底，局部加入 TUMTaRA 按钮与 Flyout 定义，并协调 Extras 菜单；不是整包覆盖 C，也不是只改 VPK 文件名。地图菜单主文件仍是独立依赖。

## 可复查证据

```text
python -X utf8 tools/check_tumtara_conflict.py
```

- 比较清单、输入身份、具体控件、优先级模型与限制：`reports/conflict_2256147202/comparison.json`。
- 主菜单全文差异：`reports/conflict_2256147202/mainmenu.res.diff`。
- Extras 全文差异：`reports/conflict_2256147202/extrasflyout.res.diff`。
- 下载元数据：`originals/TUMTARA_2256147202.json`。
