# C：按连接会话初始化，不再随 ESC 重置

本轮已部署到指定游戏目录，两个安装文件与成品逐字节一致；部署记录为
`reports/c_session_deploy/verification.json`。当前会话组件为 1.0.1，两轮全量审核以及每轮 32 项 C 回归、13 项部署故障、8 项 Evolved 配置测试与独立会话状态测试通过。
游戏未启动，真实换房和定时器投递验收仍待进行。

专项复审、已修复问题与本轮恢复包见 [C_SESSION_AUDIT.md](C_SESSION_AUDIT.md)。

## 当前变化

- 成品名称保持 `dist/【00】C_ESC_LED_血条和速度_TUMTaRA.vpk`。
- 删除 ESC 菜单中全部 **12 个 `Init_*` 固定范围初始化控件**，保留原操作控件。
- “修复黑块”和“光射角”共同控制 `r_flashlightfov`，统一恢复本机游戏原生默认 **53**。光射角滑条下限从 100 降至 50，上限仍为 200；否则打开菜单可能把 53 夹回 100。
- 雾气关闭、尸体 0、两个轮廓 0、亮度 1、光射程 3000、网络文本右上角等其他默认项不变。
- 相对本轮原件，VPK 仍有 222 个成员，仅 ESC 菜单和默认 CFG 两个成员变化；LED、血条、速度、TUMTaRA 和准星处理保持不变。

## 为什么增加配套组件

纯 VPK 的菜单构造不等于加入房间事件。现在由已有 **L4N** 插件加载器加载
`dist/c_session_helper/CSessionDefaults.dll`，在连接进入可游玩状态时排入一次
`exec l4d2esc_defaults`。没有把默认 CFG 放进每次 ESC、每次出生或地图菜单的命令中。

状态机设计：

1. 断开连接后重新待命。
2. 新网络通道，或同地址通道复用但连接时长回退，识别为新连接；负数、NaN 和无穷连接时长不消耗初始化机会。
3. 等待实际进入游戏后只执行一次；打开/关闭 ESC、同一连接的加载过程不重新待命。
4. 背景地图和录像播放不执行；不同房间/服务器重新连接后重置。

**只安装 VPK 会停止 ESC 重置，但不会自动执行入房默认项。需要同时安装 DLL。**
配套包 `dist/C_session_release.zip` 已按游戏目录相对路径包含两者和哈希清单。
DLL 是新增本地插件，不包含在 VPK 中，也没有修改游戏或 Evolved DLL。

## 兼容边界与待实测项

组件仅支持本轮已检查的 x86 `engine.dll`：
`8a6d468059394bf4cfce32f11dcba12ef45de88da1373084d5a2916d0bf7ba86`。
引擎哈希或接口槽位不匹配即停用并记日志，不猜偏移。
使用 L4N 的启动回调创建线程消息定时器；不增加工作线程调用引擎、渲染钩子、内存补丁或服务器限制修改。

**当前验证覆盖编译、独立状态模型、完整资源和文件部署，不等于游戏内验证。**
L4N 启动回调线程是否持续派发该定时器、真实换房、地图切换、在线 cvar 是否接受、
实际画面仍需实测。成功排入命令也不代表服务器接受所有参数。

启动游戏后检查根目录 `CSessionDefaults.log`：

- `READY`：组件创建定时器；不代表已收到定时器回调。
- `TIMER_ACTIVE`：1.0.1 起增加，证明启动线程至少实际派发过一次定时器回调。
- `NEW_CONNECTION`：本次连接已排入默认 CFG。
- `DISABLED`：引擎版本、接口或调用异常导致停用；按原因检查，勿盲目取消版本保护。

验收顺序：入房读取 `r_flashlightfov` 为 53 → 调至 120 → 反复 ESC 保持 120 →
同连接加载仍保持 → 离开并加入另一房间回到 53。再分别检查其他 11 项默认值。
若没有 `NEW_CONNECTION`，先排查定时器投递，切勿重新添加 ESC 初始化控件。

## 构建、审核、安装、回滚

在项目根目录运行：

```text
python -X utf8 tools/build_c_session_plugin.py
python -X utf8 tools/build_c_mod.py --width 1280 --height 720
python -X utf8 tools/c_session_release.py package
python -X utf8 tools/full_review.py
python -X utf8 tools/c_session_release.py deploy
python -X utf8 tools/c_session_release.py verify-installed
```

游戏应先退出。部署只更新 `left4dead2/addons/【00】C_ESC_LED_血条和速度_TUMTaRA.vpk`
和新增 `bin/neko/plugins/CSessionDefaults.dll`；不会修改 Evolved 配置、按键、游戏 EXE 或引擎。
原安装文件备份和部署事务在 `reports/c_session_deploy/`。
该部署器固定当前游戏目录；首次安装只接受已确认的旧 C 哈希，后续升级核对上一事务的安装哈希。
支持旧事务迁移、升级和回滚后重装，备份按 `transactions/<唯一编号>/` 隔离，旧事务和旧核验记录保留。
所有目标先检查，再使用目标目录中的私有临时文件校验后原子替换；复制中断不再留下截断的活动文件。
遇到待恢复的 PREPARED 事务，先执行回滚，再部署。它仍不是通用 EXE 安装器，也未实现并发安装器的排他锁。

项目内恢复副本（不触碰游戏）：

```text
python -X utf8 tools/c_session_release.py rollback-copy
```

生成 `dist/rollback_before_session_defaults/【00】C_ESC_LED_血条和速度_TUMTaRA.vpk`，
原件哈希 `97fa1e054d0676042b9da149b421e645aad493160db98b7f04668a2503e463da`。
这会恢复旧版 ESC 重置行为，不能与新版同时启用。

实际安装回滚先预览，再退出游戏执行：

```text
python -X utf8 tools/c_session_release.py rollback-preview
python -X utf8 tools/c_session_release.py rollback-game
```

回滚核对全部现有文件与备份哈希后，恢复**最近一次部署前**的 C 和已有 DLL；
若该次为首次新增 DLL，则重命名为带事务编号的 `.disabled` 文件，不删除活动文件。
升级回滚不等于回到最初 97fa 版 C；原初恢复副本由上面的 `rollback-copy` 单独提供。
游戏回滚只做预览；临时夹具中已实际执行升级回滚、首次回滚和重复回滚，项目内恢复副本已重读验证。
已保存的个人 cvar 不在文件回滚范围内。

## 证据与记录

- 原件：`originals/C_before_session_defaults.vpk`。
- 默认值构造调用与本机身份：`reports/c_session_inputs/inspection.json`、`client_refs.txt`。
- 完整补丁及可重放载荷：`reports/C_update.patch`、`reports/C_update_patch.zip`。
- 构建、模型测试确切命令/原样输出/退出码：`reports/c_session_plugin_build.json`。
- 两轮全量审核和回滚命令记录：`reports/full_review_verification.json`。
- C 资源构建记录：`reports/C_verification.json`。

公开接口头仅辅助理解；本机后段接口顺序不同，组件使用经本机二进制核对并绑定哈希的槽位，
不能把公开旧 SDK 的后段槽号直接套用。
