# Evolved 清理记录（2026-10-25）

> **历史操作记录，不是当前安装清单。** 本文只证明 2026-10-25 当次清理；[2026-10-26 的位置检查](L4D2Evolved_小地图位置与尺寸设置.md)又观察到 Evolved 文件存在。当前机器是否安装应重新核对，不能根据本文或旧部署记录推断。C 自身不依赖 Evolved。

2026-10-25：按用户要求，从
`E:\SteamLibrary\steamapps\common\Left 4 Dead 2`
移除已确认属于 Evolved 的 30 个文件，共 35,644,247 字节。
先完整复制、逐文件核对 SHA-256，再移除游戏侧原文件；不是永久丢弃个人配置。

## 已清理

- `Evolved/`：配置、缓存、日志、ADS 脚本和更新暂存等。
- `L4d2evomodel/`：模型配置与日志。
- `bin/neko/plugins/L4D2Evolved.dll`、`L4d2evomodel.dll`。
- 核对原包哈希的两个配套资源 VPK、三段 vrmod 音效、根目录 manifest/updatelog。
- 最后只移除计划内的空专属目录，没有递归删除共享目录。

L4N、C、`CSessionDefaults.dll`、游戏 EXE、渲染组件、玩家配置和 addonlist 的前后哈希相同。
清理后 C 安装核验通过。另修正 C 部署脚本对 Evolved DLL 的多余检查：它只依赖 L4N，
在没有 Evolved 的夹具下 13 项部署测试全部通过。没有重编译或替换 C 的游戏文件。

## 备份、核验、恢复

- 完整备份：`F:\Project\03_Game_Tools\14_L4D2_ESC\reports\evolved_cleanup\backup`
- 路径/原哈希/保护项：`reports/evolved_cleanup/plan.json`。
- 清理事务：`reports/evolved_cleanup/transaction.json`，状态 `ARCHIVED`。
- 清理核验：`reports/evolved_cleanup/verification.json`。
- 无 Evolved 的 C 部署测试：`reports/evolved_cleanup/c_without_evolved_tests.json`。

```text
python -X utf8 tools/cleanup_evolved.py verify
python -X utf8 tools/cleanup_evolved.py restore-preview
```

以上两项已执行通过。确需恢复时退出游戏，运行
`python -X utf8 tools/cleanup_evolved.py restore`，会核验备份并保护后来出现的冲突文件。
实际游戏恢复未执行。

项目内的原包、研究资料和历史部署记录保留；旧“已部署 Evolved”说明为历史状态，
不要仅因历史任务自动重新安装。工坊订阅未修改；如仍订阅，Steam 可能再次下载外层包，
这不代表已经重新部署平台。此次也未安装 Skeeto、未启动游戏。
