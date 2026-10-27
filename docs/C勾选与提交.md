# C 1.3.1：勾选＋即时提交

## 操作

10 个二值设置使用真实勾选框。**勾选立即提交 1，取消立即提交 0**，无需另按应用按钮或再次开关 ESC。二值项仍集中前置，其余数值项保持原顺序和滑条形式。

勾选的含义依照文字：电视亮度模式、显示字幕、显示游戏提示、关闭角色轮廓、关闭远处物品轮廓、显示导演强度信息、地图全亮、导航网格编辑、覆盖地图雾参数、显示雾气。两个“关闭轮廓”项不勾选才是不禁用轮廓。

必须成套安装 `dist/C_session_release.zip` 中的 VPK 与 **CSessionDefaults.dll 1.3.1**，使用现有 L4N。单独更新 VPK 或保留 DLL 1.3.0 会缺少提交桥接。[下载 v1.3.1](https://github.com/STC214/L4D2-ESC-Enhanced/releases/tag/v1.3.1)，旧 v1.3.0 附件保留。

## 完整提交链路

1. 使用已核对注册函数及构造器的 `CvarToggleCheckButton_GameUI`，每项具有唯一 `C_ESC_BOOL_<参数名>` 名称，导航同步更新。
2. DLL 校验本机 `gameui.dll` SHA-256、原生方法/vtable 与处理函数完整指令边界，在实际窗口线程安装一处 5 字节内存事件转发。只对这 10 个名称且参数绑定匹配的控件补充提交，其他选项界面保留原处理。
3. 用户改变勾选状态后调用原生 `ApplyChanges` 并读回。材质参数可能到后续渲染帧才更新：首次读回仍是旧值时先记为 PENDING，最早 100ms 后由窗口定时器确认，未确认且到 1 秒阈值后记 TIMEOUT；实际检查时刻受游戏消息循环调度影响，不是严格的生效时限。不会仅因第一次读到旧值就立即 Reset。确定的标志异常才立即 Reset；超时后原生绘制同步实际值，不持续重试、锁值，也不保留 UI 面板指针。
4. 初始显示、重开 ESC、参数刷新若与实际值一致，不重复提交。没有持续锁值或每次 ESC 重置默认值。

游戏原始 DLL 文件不被修改。事件转发仅存在于进程内存，退出游戏即消失；DLL 与 GameUI 模块保持到进程退出，更新/回退应先退出游戏。未知 GameUI 版本不套用旧偏移，日志记录 `CHECKBOX_DISABLED`。

## 日志与实机测试

启动后查看游戏根目录 `CSessionDefaults.log` 的本次会话记录：

```text
CHECKBOX_READY: scoped C_ESC_BOOL controls commit through native ApplyChanges with readback; game files unchanged
CHECKBOX_COMMIT_VERIFIED: mat_fullbright requested=1 actual=1; flags unchanged=1
CHECKBOX_COMMIT_VERIFIED: mat_fullbright requested=0 actual=0; flags unchanged=1
```

`CHECKBOX_COMMIT_PENDING` 表示等待后续渲染帧，随后成功记录 `CHECKBOX_COMMIT_VERIFIED ... deferred=1`。`CHECKBOX_COMMIT_TIMEOUT` 表示窗口内未确认，不能据此断言从未应用；它也可能已被服务器再次覆盖。`CHECKBOX_COMMIT_FAILED` 保留给即时确定的异常。`READY` 不表示所有服务器必定接受全部参数，本组件不移除标志或持续对抗复制。

建议先在同一地图勾选/取消“地图全亮”，确认画面与上述读回；再检查其余 9 项，并验证手动值在反复 ESC 后仍保持。字幕、提示等功能需要对应游戏情境；轮廓/雾/导航还受服务器、地图和其他模组影响。

## 审查与产物

- 原生 x86 测试实际执行安装、trampoline、事件转发和卸载；覆盖 10 项双向提交、重复/初始通知不写值、提交拒绝后的 Reset、错名称/错绑定/非法槽/其他线程不代提交、未知处理函数拒绝接入。
- 自动化还覆盖 0～3 四个有效槽位的独立父变量隔离；这是受控测试覆盖，不表示已实测全部分屏/服务器组合。不同阶段测试次数会变化，以当前构建报告中的字面输出为准，不把旧阶段的 116/38 次统计当作最终测试总数。
- 最终审查实机日志发现旧即时确认对“地图全亮”产生 6 次误判，成功参数已有 9 条实际读回；原日志固定在 `reports/c_checkbox_bridge/runtime_before_deferred.json`。追加延迟生效、快速开关取消排队、原生绘制刷新不代提交、死 CVar 指针及超时不重试测试。窗口测试目录改为 PID＋运行时刻，避免 PID 复用误读旧成功日志。前一条的统计是上一轮记录，不是本次最终测试数量。
- 原生处理代码重放与上述受控测试不冒充真实游戏点击测试，实机表现仍需确认。
- 对比上次两档版本，VPK 仅修改 ESC 菜单，其他 222 个成员不变；配套 DLL 升级 1.3.1。天气/尸体/光照默认项、手电贴图/shader、聊天/HUD 保留。
- 完整验证：`reports/c_current_review/verification.json`。
- 本轮基线、字面命令与输出、补丁重放及成套回滚：`reports/c_checkbox_bridge/verification.json`。
- 本轮补丁：`reports/c_checkbox_bridge/patch.zip`、`menu.patch`。
- 成品：`dist/【00】C_ESC_LED_血条和速度_TUMTaRA.vpk` 与 `dist/c_session_helper/CSessionDefaults.dll`。

## 部署与回退

```text
python -X utf8 tools/review_c_session_deployment.py --deploy
python -X utf8 tools/c_session_release.py verify-installed
python -X utf8 tools/c_session_release.py rollback-preview
python -X utf8 tools/c_session_release.py rollback-game
```

回退使用最近一次本机事务备份，恢复该次部署前的成套文件；必须先退出游戏。早期两档阶段原件另保存在 `originals/C_before_checkbox_commit.vpk` 和 `originals/CSessionDefaults_before_checkbox_commit.dll`，并非每次更新的即时回退目标。
