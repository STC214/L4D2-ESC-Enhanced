# C：TUMTaRA 主菜单合并与速度布局恢复

## 当前产物

- 安装包：`dist/【00】C_ESC_LED_血条和速度_TUMTaRA.vpk`，222 个成员；后续成品固定使用此名，路径统一定义在 `tools/release_paths.py`。
- SHA-256：`97fa1e054d0676042b9da149b421e645aad493160db98b7f04668a2503e463da`。
- 基底：`originals/C_before_tumtara_merge.vpk`，即上次完整审核后的 C，221 个成员。
- 基底 SHA-256：`5eb9113d019b750f00827128bbfb1bcd331feae7e05e23a8dcfa036270a06e0e`。

## 合并方案和实际改动

没有用 TUMTaRA 的整个主菜单覆盖 C。相对上次 C，只修改三个既有文本资源、新增一个资源；其余 218 个成员逐字节不变：

| 资源 | 改动 |
|---|---|
| `resource/ui/l4d360ui/mainmenu.res` | 加入 TUMTaRA、控制台、服务器浏览器、重载 UI 按钮及 FlyoutMenu；原控件完整保留，仅为成就/选项/附件增加右向导航 |
| `resource/ui/l4d360ui/more/flmtumtara.res` | 从官方主文件取得真正的地图启动菜单，逐字节导入，避免只有入口却缺菜单 |
| `scripts/hudlayout.res` | `CItemPickupPanel.ypos` 从 0 恢复来源默认 180；排除来源准星、既有审核修复仍保留 |
| `resource/ui/hud/itempickup.res` | 恢复来源原字节，数字速度、最大/平均速度与速度仪表盘全部恢复来源默认位置；计时器也恢复原父子坐标组合，屏幕位置不变 |

保留 C 的全屏 ESC、所有既有选项、12 项默认值、右上角网络信息、LED、本人/队友正常及倒地血条、原有准星，以及之前的速度数字计算修复。没有修改角色移动速度，也没有改游戏目录或个人配置。

TUMTaRA 入口沿用来源按钮位置 `(300,255)`、其余按钮 `(300,275)` / `(300,295)`。FlyoutMenu 使用与原菜单背景一致的 `400×290` 真实尺寸、比例坐标和 `tum_l4d2_1` 初始焦点，保留来源相对偏移 `(-200,-120)`。有限的“按钮原点/按钮右缘”两种锚点模型均在最小 `640×480` 逻辑画布内；这不等于已观察 L4D2 的实际定位实现，最终弹出位置和点击需游戏验证。

## 安装与依赖：重要

1. 退出游戏，只安装新的 `dist/【00】C_ESC_LED_血条和速度_TUMTaRA.vpk`；停用旧 C、A、B、独立来源 HUD、独立 LED，以及独立的 **2256147202 主菜单按钮包**，避免重新争用主菜单和工具箱。
2. **保留/安装 [TUMTaRA Main Files 469986973](https://steamcommunity.com/workshop/filedetails/?id=469986973)**。C 合并的是按钮和实际菜单资源，不打包地图、模型及地图脚本。菜单显示不代表地图已安装。
3. 已下载的完整原始地图依赖也保存在 `originals/TUMTARAMAIN_469986973.vpk`，未修改；若采用本地安装方式，可单独安装它，不要和同一工坊主包重复安装。
4. 原菜单中的其他专用测试地图、天空盒地图按钮原样保留，需要对应的额外地图包；主文件只包含四张 `tumtara*` 主地图。没有为了消除报错删除原作者的其他菜单项。
5. 重启游戏，在主菜单检查 TUMTaRA 入口、展开菜单、主地图加载，再进图检查 ESC、血条、速度数字/指针和准星。作者提示地图应在游戏刚启动后加载，见[主文件说明](https://steamcommunity.com/workshop/filedetails/?id=469986973)。

网络图仍按已确认的 `1280×720` 配置打包；换分辨率后用现有 `--video` 或宽高参数重建，不宣称已经实现游戏运行时自适应。

## 验证与回滚

```text
python -X utf8 tools/build_c_mod.py --width 1280 --height 720
python -X utf8 tools/verify_tumtara_merge.py
python -X utf8 tools/full_review.py
python -X utf8 tools/rollback_tumtara.py
```

四类交付文件：

- 修改产物：`dist/【00】C_ESC_LED_血条和速度_TUMTaRA.vpk`。
- 本轮文本差异：`reports/C_tumtara_merge.patch`；可执行累计补丁包 `reports/C_update_patch.zip`，使用 `python -X utf8 tools/build_c_mod.py --apply-patch` 重放，从最早 C 基底重建最新 C。
- 验证记录：`reports/C_verification.json`（准确命令、输入哈希、原样 stdout/stderr 和退出码）；全量两轮记录 `reports/full_review_verification.json`。
- 可运行回滚：`tools/rollback_tumtara.py`，生成并重新核验 `dist/C_before_tumtara_restored.vpk`，恢复本轮前的 C，包括旧主菜单和左上角速度布局；不覆盖当前产物或游戏文件。

全量审核现覆盖所有 VPK 成员 CRC、142 个 KeyValues 资源、79 个纹理、30 项回归/故障注入测试、五种分辨率、补丁重放与回滚。验收区分：原合并基底没有 TUMTaRA 入口且速度位于左上角；新包有完整菜单引用链且速度控件回到来源默认位置。

## 固定命名后的复审

- 本次只统一输出路径并加强审核器，VPK 内容不变，SHA-256 与合并交付版相同。
- 新增固定文件名一致性测试，以及按钮越界、弹窗偏移越界、控制台命令损坏三个故障注入测试。后三项曾暴露审核盲点，已修复：检查新增控件的完整字段，并使用实际资源中的坐标/尺寸计算边界，不再依赖写死的示例坐标。
- 命名前备份为 `originals/C_before_fixed_filename.vpk`；旧名历史副本在 `dist/history/C_fullscreen_esc.vpk`。
- `python -X utf8 tools/verify_release_name.py` 验证新旧文件内容一致；`python -X utf8 tools/rollback_release_name.py` 生成 `dist/rollback_before_fixed_filename/C_fullscreen_esc.vpk`，不改当前成品或游戏目录。
- 本轮两次从头构建的全部命令与退出码仍记录于 `reports/full_review_verification.json`，上面的 TUMTaRA 回滚只用于回退更早的合并行为。

项目内未运行 L4D2。实际菜单位置/输入、地图加载、血条与速度刷新、服务器 cvar 接受情况仍待游戏验证；静态零错误不是游戏“绝无问题”的保证。
