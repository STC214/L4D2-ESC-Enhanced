# 文档索引

当前 C 版本：**1.3.1（预发布）**。当前说明、版本记录、研究材料和历史方案分开阅读；历史文档中的“当前/最新”只指其写作阶段。

## 当前 C：安装与维护

| 文档 | 内容 |
|---|---|
| [C 使用说明](C使用说明.md) | 下载、依赖、成套安装、默认项、网络图、卸载及最近事务回退 |
| [勾选与提交](C勾选与提交.md) | 10 个开关的语义、原生提交、延迟确认、日志和兼容边界 |
| [开发与验证](开发与验证.md) | 构建条件、当前工具入口、审查证据、部署与发布注意事项 |
| [项目首页](../README.md) | 当前功能与快速安装入口 |

## 平台研究：不是 C 自带功能

以下是对特定版本/检查时刻的记录，不是对当前工坊最新版或当前机器安装状态的持续保证。小地图/世界导航由相应平台提供，不由 C 提供。

- [平台来源、下载逻辑与功能冲突清单](平台来源与功能冲突清单.md)
- [Evolved 小地图位置与尺寸设置](L4D2Evolved_小地图位置与尺寸设置.md)
- [Evolved 适配流程与未来 EXE 规范](L4D2Evolved_自动适配流程与EXE实现规范.md) — 设计资料，EXE 尚未实现
- [Evolved 清理记录](Evolved清理记录.md) — 当次清理记录，不代表此后从未重新安装
- 机器可读资料：[平台元数据](workshop-platforms.json)、[适配规则 v1](evolved-adaptation-rules.v1.json)

## 版本发布记录

以对应标签的发布包为准，旧版本说明不替代当前教程；本机 `dist/` 与 `reports/` 是可再生成的工作目录，历史文件可能已清理。

- [v1.3.1：勾选提交与延迟确认](releases/v1.3.1.md)
- [v1.3.0：轮廓默认项与手电整合](releases/v1.3.0.md) — 勾选提交缺陷由 1.3.1 修复
- [v1.2.4：同图重载](releases/v1.2.4.md)
- [v1.2.3：进图光圈 165](releases/v1.2.3.md)
- [v1.2.0：天气/尸体默认项](releases/v1.2.0.md)

## 历史归档：用于追溯，不照抄安装

原文保留并增加归档标记，Markdown 内部链接已按新位置调整。代码块中的项目路径仍按项目根目录解释；研究数据和原始基线未随文档移动。

| 阶段 | 归档 |
|---|---|
| 旧首页、B 全屏菜单与累计阶段记录 | [历史 README](archive/README_B_TO_C_HISTORY.md)、[原始分析](archive/ANALYSIS.md) |
| LED、网络图与 HUD 初次整合 | [C 旧说明](archive/C_README.md)、[HUD](archive/C_HUD_INTEGRATION.md) |
| TUMTaRA 冲突与局部合并 | [冲突检查](archive/TUMTARA_CONFLICT.md)、[合并记录](archive/C_TUMTARA_INTEGRATION.md) |
| 会话默认项、首次 ESC 及审查演进 | [默认项](archive/C_SESSION_DEFAULTS.md)、[菜单合并](archive/C_MENU_CONSOLIDATION.md)、[专项审查](archive/C_SESSION_AUDIT.md)、[早期全量审核](archive/FULL_AUDIT_REPORT.md) |
| 已被替换的右下聊天布局 | [旧聊天布局](archive/C_CHAT_BOTTOM_RIGHT.md) |
| 临时恢复两档滑条 | [过渡修复与分组](archive/C开关修复与排列.md) |
| 独立手电测试，现已整合进 C | [末端淡出测试](archive/FLASHLIGHT_NOFADE_TEST.md)、[RGB 增益测试](archive/FLASHLIGHT_GAIN2X_TEST.md) |
| Evolved 1.2.5 初次研究/适配/部署 | [使用研究](archive/evolved/使用方法与研究记录.md)、[本机适配](archive/evolved/本机游戏适配方案.md)、[部署与地图入口](archive/evolved/部署结果与地图导航入口.md) |

## 文档管理约定

- `README.md` 只描述当前 C，不堆叠早期安装步骤。
- 所有业务 Markdown 放在 `docs/`；`docs/archive/` 是阶段材料，`docs/releases/` 是版本记录。
- `AGENTS.md` 保留根目录，作为生效的工作区规则；`reports/` 的自动生成报告不作为业务教程移动。
- 核心日志/审查报告通常不提交 Git；资料里列出的本地路径不意味着 GitHub 下载 ZIP 包含这些证据或基线。
