# C：二值控件修复与 ESC 设置分组

> **历史归档，不是当前安装教程。** 原路径：`docs/C开关修复与排列.md`。文中的“当前/最新/本轮”均指当时阶段；旧默认值、布局、哈希和回退命令不代表 C 1.3.1。当前使用见 [C 使用说明](../C使用说明.md)，完整分类见 [文档索引](../INDEX.md)。代码块与反引号中的项目路径仍按项目根目录解释；部分历史试验包/恢复副本已清理，原始输入与核心审查证据保留。


> 历史过渡版本：后续已按要求实现勾选＋即时提交，见 [本地 1.3.1 说明](../C勾选与提交.md)。本文保留临时恢复两档滑条的记录。下述 `0x10004550` 是 GameUI 模板的事件实现；新版本明确选择 `CvarToggleCheckButton_GameUI` 工厂，以保证控件 ABI 与提交桥接一致。

## 结论与修复

用户实测“地图全亮”无效后，检查已交付的 C 1.3.0 及本机 `bin/gameui.dll`。原生 `CvarToggleCheckButton` 的勾选处理（VA `0x10004550`）发送 `ControlModified`，本身不调用参数 setter；写值位于独立的 `ApplyChanges`（VA `0x10004500`）。本 ESC 菜单没有补齐即时提交，单纯改控件类名造成回归，不是默认值或手电 shader 问题。

通过固定哈希的原生处理代码重放，0→1 和 1→0 两个方向的点击处理均为 0 次 setter 调用；显式调用 ApplyChanges 才写值。VGUI 依赖用桩替代，此证据不冒充真实游戏点击测试。已发布资源中的 10 项使用相同控件与事件路径，全部受此缺陷影响。

按用户确认，本轮恢复此前可用的原生 `SliderControl` 直接设置路径，保留内嵌控件，范围 0～1、步进 1；不再使用有缺陷的勾选框。0 表示不启用标题描述的效果，1 表示启用。

## 前置二值项

按原相对顺序，排在设置区前面（先左列从上至下，再右列从上至下）：

| 顺序 | 文案／值 1 的含义 | 参数 |
|---:|---|---|
| 1 | 电视亮度模式 | `mat_monitorgamma_tv_enabled` |
| 2 | 显示字幕 | `closecaption` |
| 3 | 显示游戏提示 | `gameinstructor_enable` |
| 4 | 关闭角色轮廓 | `sv_disable_glow_survivors` |
| 5 | 关闭远处物品轮廓 | `sv_disable_glow_faritems` |
| 6 | 显示导演强度信息 | `director_show_intensity` |
| 7 | 地图全亮 | `mat_fullbright` |
| 8 | 导航网格编辑 | `nav_edit` |
| 9 | 覆盖地图雾参数 | `fog_override` |
| 10 | 显示雾气 | `fog_enable` |

其余数值项目接续填入剩余位置，保持修复前的相对顺序。雨量和光亮度虽也有 0～1 范围，但属于连续数值，不混入二值分组。同步更新上下左右键导航及进入设置区的导航入口。

两个“关闭轮廓”仍默认 0，即不禁用轮廓。服务端复制、游戏模式及地图对变量的限制仍然存在，本修复不删除变量标志，也不承诺任意服务器都接受更改。

## 范围与验证

- 与用户测试的 C 1.3.0 比较，只改 `resource/ui/l4d360ui/ingamemainmenu.res` 一个成员，其余 222 个成员逐字节不变。
- DLL 仍为 1.3.0 且哈希不变；手电贴图/shader、天气/尸体/轮廓默认值、聊天及其他 HUD 均不改。
- 二值组和剩余组分别保持原相对顺序；整包回归增加排序断言，共 48 项。
- 菜单单项补丁、重放与回滚记录：`reports/c_switch_events/verification.json`。
- 原生事件重放证据：`reports/c_switch_events/investigation.json`。
- 补丁：`reports/c_switch_events/patch.zip`、`menu.patch`。
- 原件：`originals/C_before_switch_event_fix.vpk`，SHA-256 `143f48cc557ee9031e12742966e772aeac13fff7bd7674cdcfc163a08855f0e9`。
- 成品仍为 `dist/【00】C_ESC_LED_血条和速度_TUMTaRA.vpk`。

## 本轮部署与回退

使用现有成套事务入口，不重新启用已整合的独立手电测试包：

```text
python -X utf8 tools/review_c_session_deployment.py --deploy
python -X utf8 tools/c_session_release.py verify-installed
python -X utf8 tools/c_session_release.py rollback-preview
python -X utf8 tools/c_session_release.py rollback-game
```

本轮回退恢复部署前的 C 1.3.0 和原样 DLL，依赖本机备份。旧三文件整合事务仅记录上一次整合部署，不用于回退这次菜单更新。

当前是本地后续修复，不表示 GitHub 的 v1.3.0 附件已被替换。静态与重放验证通过后，仍需实机确认地图全亮及其他控件的实际效果。
