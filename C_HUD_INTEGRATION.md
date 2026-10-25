# C：集成 3230782214 的非准星 HUD 功能

> **后续更新：速度表与速度仪表盘已按新要求恢复来源默认位置，最新 C 为 222 个成员并集成 TUMTaRA。** 见 [当前合并说明](C_TUMTARA_INTEGRATION.md)。下文的左上角平移、221 成员和旧回滚是初次 HUD 集成的历史记录。

> 后续已进行全量审核修复，最新结果见 [FULL_AUDIT_REPORT.md](FULL_AUDIT_REPORT.md)。四位当前速度数字、少量材质和重复控件标识已进一步修复。

## 安装与效果范围

- 最新包固定为 `dist/【00】C_ESC_LED_血条和速度_TUMTaRA.vpk`。
- 停用旧 C、独立的 3230782214 HUD 和独立 LED 模组，只启用这个合并版。
- C 的全屏 ESC 菜单、12 项默认参数、右上角网络信息、LED 手电以及原有准星资源全部保留。
- 合入来源模组的本人/队友血条、倒地血条、血量数字、速度仪表与数字、最大/平均速度、计时器、计分板、聊天布局、互动进度条和其他 HUD 显示资源。
- 当前速度表/仪表盘整组采用来源默认位置；没有启用 `cl_showpos`，因此不会额外叠加坐标和视角诊断信息。
- 本次没有向实际游戏安装目录写入文件，也没有改动任何角色移动速度参数。

## 来源与身份

来源：[B4B Modified HUD & UI（添加速度表版本）](https://steamcommunity.com/sharedfiles/filedetails/?id=3230782214)，工坊作者所罗门的战神。其说明中的原作/改版来源链接保存在下载元数据 `originals/HUD_3230782214.json`，没有更改来源作者信息。

- 原包：`originals/HUD_3230782214.vpk`。
- 原包 SHA-256：`3d973dcf9101dc0d21dbd80eb116b7b368a69b8a8b669fb6a72b18dd8254a885`。
- 解包证据：`extracted/HUD/`，原件及解包原文均保留。
- 集成前的 C：`originals/C_before_speed_display.vpk`。
- 集成前 C 的 SHA-256：`89b3517b10a5e63a9abe9e98323c5d2b854c971ce1dc50fb58a2c12eedbca8c7`。

## 速度读取实现：观察，不是臆造

来源模组的速度表位于 `resource/ui/hud/itempickup.res`，使用 ImagePanel 绘制仪表、指针与数字帧。

`materials/vgui/hud/arrow.vmt` 的 `PlayerSpeed` 代理取得玩家速度，将值传入旋转计算与纹理变换；当前速度数字材质 `digits_8.vmt`、`digits_17.vmt`、`digits_18.vmt`、`digits_19.vmt` 同样以 `PlayerSpeed` 作为数据源，计算 `$frame`。指针材质保持原字节；四位数字材质在后续审核中修正了取位错误，见全量审核报告。

因此合并版通过来源模组已具备的引擎材质代理显示动态速度，不是在 ESC 菜单中写一个静态数字，也不是扫描进程内存。具体速度单位、水平/三维速度定义、观战时的数据对象及最大/平均值复位行为沿用来源模组，未在本机游戏运行中核实。

## 排除准星

1. 从 `scripts/hudlayout.res` 排除 `CustomCrosshair` 和来源模组的 `HudCrosshair` 覆盖块。
2. 从 `resource/ui/hud/localplayerpanel_incap.res` 排除倒地 `CustomCrosshair`。
3. 不导入来源模组的 `materials/vgui/hud/altcrosshair.vmt`、`altcrosshair.vtf` 和 `xbox_reticle.vtf`。
4. 不设置 `crosshair 0`，不修改 C 已有准星开关、颜色、材质或调节范围。
5. 来源和 C 还存在 `hud/hmm.vmt` / `hmm.vtf` 同名冲突：来源版本及自身纹理引用改入 `materials/vgui/c_hud3230782214/hud/`，C 原文件保留。

## 初次集成的布局修改与保留（历史；平移已撤回）

- 原仪表依附于 `CItemPickupPanel`，父面板纵坐标为 180。直接把子控件设为负坐标可能受到父面板裁切，因此改为父面板 `ypos=0`、保留全屏大小。
- 17 个速度相关子控件统一平移：`x -= 172`，`y -= 128`。逻辑边界为 `(12,12)` 至 `(138,156)`，位于左上角且保留屏幕边距；内部相对位置、尺寸与材质绑定保持原样。
- 所有非速度子控件 `y += 180`，抵消父面板的平移，使计时器等控件的原屏幕位置不变。
- 本人/队友、正常/倒地的 HealthPanel 及动态血量标签均保留。
- 原包的 `teammatepanel_incap.res` 尾部多一个 `}`，导入时去掉这个多余的结束括号；后续审核还修正了 DownSign 与头像重复的控件标识，保留血量绑定。
- 不导入原包的说明文件、三份 Paint.NET 工程及一份 TGA 源图；它们不属于这里的运行资源。原文件仍在解包目录。

## 验证结果与限制

- 来源原包共 153 个成员，选入 145 个运行资源。
- 更新前 C 为 76 个成员，最新 C 为 221 个成员；在当前 1280×720 配置下，75 个原成员逐字节保持不变，仅 ESC 菜单的一个重复控件标识因后续审核而修正。
- 校验所有 VPK 成员 CRC、来源身份、排除准星、冲突资源隔离、血条入口、速度材质数据源、17 个速度子控件边界，以及全部导入 RES 的括号结构。
- 验证分辨率生成 640×480、1280×720、1920×1080、2560×1440、3840×2160。网络图继续按原先的打包时视频配置方案适配，未变成运行时自适应。
- 更新补丁已重新打包并重放，重放产物与最新 C 完全一致。
- 游戏实测仍待进行：HUD 加载、速度实时刷新/观战数据、临时血量与倒地动画、分屏和不同游戏模式、在线服务器模组限制。静态材质绑定不是实时运行证据。

## 复现、补丁与回滚

```text
python -X utf8 tools/build_c_mod.py --width 1280 --height 720
python -X utf8 tools/verify_hud_integration.py "dist/【00】C_ESC_LED_血条和速度_TUMTaRA.vpk"
python -X utf8 tools/build_c_mod.py --apply-patch
python -X utf8 tools/rollback_hud.py
```

- 完整补丁包：`reports/C_update_patch.zip`。基底仍是最早的 C，内含 LED 和 HUD 整合的累计载荷，清单记录准确输入哈希。
- 可读文本差异：`reports/C_update.patch`。
- 命令、输入哈希、原样 stdout/stderr 与退出码：`reports/C_verification.json`。
- 本次回滚脚本：`tools/rollback_hud.py`，产生 `dist/C_before_hud_restored.vpk`；已验证与这次集成前 C 完全一致。
- 回滚不操作已安装的游戏文件或个人配置；若要切回旧 C，退出游戏后只安装恢复副本。
