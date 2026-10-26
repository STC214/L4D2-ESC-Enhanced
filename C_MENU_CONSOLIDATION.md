# C：重复选项合并、天气关闭与首次 ESC 手电光圈

> **当前版本更新（1.2.3）：** 已移除首次 ESC 设置光圈的逻辑，改为每关进入时按天气系统相同路径设置光圈 165；之后可手动调整。详见 [当前说明](docs/releases/v1.2.3.md)。本文以下首次 ESC 150 等内容是历史设计记录，不代表当前行为。

> **后续聊天布局更新：** 聊天历史和输入行已改为右下方；本轮只相对菜单合并版修改两个聊天资源。最新审查记录与回滚入口见 [C_CHAT_BOTTOM_RIGHT.md](C_CHAT_BOTTOM_RIGHT.md)，以下菜单合并差异保留作历史说明。

## 本轮成品

- VPK：`dist/【00】C_ESC_LED_血条和速度_TUMTaRA.vpk`，固定名称不变，222 个成员。
- 自动化配套：`dist/c_session_helper/CSessionDefaults.dll`，版本 **1.1.0**。
- 两件套安装包：`dist/C_session_release.zip`，按游戏目录相对路径打包。
- 修改与补丁：`reports/c_menu_consolidation/menus.patch`、`patch.zip`。
- 完整审查记录：`reports/c_menu_consolidation/verification.json`。

已按后续指令部署到 `E:\SteamLibrary\steamapps\common\Left 4 Dead 2`：VPK 与 1.1.0 DLL 均与项目成品哈希一致，旧文件已按事务备份，回滚预览通过；部署记录为 `reports/c_session_deploy/verification.json`。尚未启动游戏验证运行效果。旧版说明中的两处手电滑条、重复下拉菜单和 1.0.1 组件属于历史状态。

## 选项合并

原成品有 18 组重复参数。合并后全部 49 个独立参数仍有入口，每个参数在 C 的 RES 中只有一个 `conCommand` 控件：

| 设置 | 唯一保留入口 |
|---|---|
| 游戏音量、音乐音量 | 音频设置页；保留开局前也能调整音量的原有音频菜单 |
| 准星、网络图、雨量、雪量、雾覆盖 | ESC 主面板；删除重复的旧下拉入口及其参数控件 |
| 光射角／修复黑块 | ESC 的 **手电光圈**，`r_flashlightfov`，范围 50–200 |
| 视左移／视右移 | ESC 的 **第三人称左右偏移**，`c_thirdpersonshoulderoffset`，范围 −1000–1000 |

重排了剩余滑条，并修复删除控件后的导航引用，以及原有 `QuickKickPlayer → DrpPrecisionAssist` 悬空引用。保留完整背景、其他独立设置、LED、血条、速度仪表和 TUMTaRA；本轮仅修改五个已存在的文本成员，其他 217 个成员字节不变。三个旧下拉资源仍保留在包内，但已没有重复参数写入器，也不再由 ESC 旧入口打开。

## 默认值与首次 ESC

| 参数 | 值 | 执行时机 |
|---|---:|---|
| `r_RainParticleDensity` | 0 | 新连接进入游戏时一次 |
| `r_SnowParticles` | 0 | 同上 |
| `fog_override`（迷雾／雾覆盖） | 0 | 同上 |
| `fog_enable`（雾气开启） | 0 | 同上 |
| `r_flashlightfov` | 53 | 保留原有入房默认值；尚未按首次 ESC 时使用 |
| `r_flashlightfov` | **150** | 每张可游玩地图首次按 ESC 时一次 |

首次 ESC 后可以在 50–200 范围内手动调节，包括低于 150 的数值；再次 ESC 不重置，不采用 `minValue=150` 或固定范围滑条。下一关、观察到加载状态后的同图重载、重新连接会为手电光圈重新待命；其他默认设置仍按原规则只在新连接时初始化。

实现沿用已安装的 L4N 插件接口和原有引擎版本/槽位校验，不改游戏二进制。线程局部 `WH_KEYBOARD` 仅观察本游戏前台窗口的首次 ESC 按下，不拦截或重映射输入；键盘回调只记录事件，引擎命令仍由原来的启动线程定时器排入。游戏主菜单、未进入地图、背景地图及录像播放不会消耗地图初始化机会。

**自动入房默认项和精确首次 ESC 行为需要同时更新 DLL。VPK 单独包含合并后的界面和默认 CFG，不自行加载 DLL。** 本轮保持现有 x86 引擎 SHA256 白名单：`8a6d468059394bf4cfce32f11dcba12ef45de88da1373084d5a2916d0bf7ba86`，其他引擎版本停用组件，不猜测偏移。

## 构建、复查、回滚

```text
python -X utf8 tools/build_c_session_plugin.py
python -X utf8 tools/build_c_mod.py --width 1280 --height 720
python -X utf8 tools/full_review.py
python -X utf8 tools/build_c_mod.py --apply-patch
python -X utf8 tools/c_menu_consolidation.py rollback-copy
```

`build_c_mod.py` 默认已指向本轮构建层，仍支持 `--video` 和指定分辨率；`--legacy-session` 仅用于复现旧版。新构建层的固定基线为 `originals/C_before_menu_consolidation.vpk`，SHA256 为 `b6b4819c711728d5a647ca341f1c93aef480294171bc55b824e3f0bcb58dc650`。

回滚命令生成并校验 `dist/rollback_menu_consolidation/` 下的原 VPK 和原 1.0.1 DLL。退出游戏后，分别将两个回滚文件复制回 `left4dead2/addons/` 和 `bin/neko/plugins/`。回滚两件套必须一起替换，不要同时启用新旧 VPK。

## 验证边界

完整审查覆盖全部 VPK 成员、纹理与资源语法、布局/导航、40 项 C 回归及故障注入、13 项部署事务夹具、原生会话/首次 ESC 状态机、真实 x86 DLL 加载与导出接口、补丁重放、回滚副本及确定性打包。状态测试包含首次设 150 后手动改成 80、再按 100 次 ESC 仍保持 80。

两轮通过只表示静态及自动化检查范围内未发现问题，不等于游戏内效果已经验收。仍需进图查看日志 `TIMER_ACTIVE`、`INPUT_READY`、`NEW_CONNECTION` 和 `FIRST_ESC`；检查每关首次 ESC、同图重载、手动低于 150 后反复 ESC、服务器参数接受情况、实际文字/画面、Alt-Tab 和窗口焦点。组件错误记录为 `INPUT_ERROR` 或 `DISABLED`。
