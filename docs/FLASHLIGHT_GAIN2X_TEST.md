# 手电测试版：无末端淡出 + RGB 2 倍

> 历史独立测试记录：此版本已整合进 C 1.3.0。使用新版 C 时停用独立 `C_flashlight_nofade_TEST.vpk`，当前安装方式见 [C 使用说明](C使用说明.md)。以下保留测试阶段原记录。

本版基于用户已反馈末端淡出抑制有效的测试 shader，仅在其手电颜色乘法后增加一条逻辑 RGB 加法，实现渲染通道贡献乘二。保留已有无淡出修改，不改变贴图、光圈、射程、DLL、全局曝光或其他光源。

## 安装产物与当前部署

- 成品：`dist/flashlight_gain2x_test/C_flashlight_nofade_TEST.vpk`
- 本机目标：`E:\SteamLibrary\steamapps\common\Left 4 Dead 2\left4dead2\addons\C_flashlight_nofade_TEST.vpk`
- 与旧独立测试包同名替换，不要同时启用多个提供同一 shader 的包。
- C 仍使用普通 DXT5、均值约 190 的贴图，光圈 165、射程 3000；本版不写这些参数。

## 验证与观察

全部 2,832 个 shader 程序均重新解包，与内存探针逐一比对，并通过 `D3DDisassemble`。每个只新增一条 RGB ADD，无新增纹理采样、寄存器或光源。

这证明字节码及重打包符合所验证结构，**不等于实测屏幕亮度翻倍**。后处理、自动曝光、HDR/LDR 和材质仍可能影响最终显示。实际性能也尚未测量。

重启游戏后，在原先同一场景比较远处物体、暗色墙面和近处白墙。留意亮部过曝或细节丢失；保留其他设置，避免同时调贴图和 gamma。仅覆盖 `flashlight_ps30`，独立眼睛/牙齿等 shader 不在本轮覆盖范围。

## 构建与安装检查

```text
python -X utf8 tools/build_flashlight_gain_test.py
python -X utf8 tools/deploy_flashlight_nofade_test.py --variant gain2x verify
```

构建及原样反汇编记录：`reports/flashlight_gain2x_test/independent_verification.json`。
补丁及可重放数据：`reports/flashlight_gain2x_test/patch.zip`。
本机部署备份与事务：`reports/flashlight_gain2x_test/deployment.json`。

## 回退至原先仅无淡出版本

退出游戏，在项目目录运行：

```text
python -X utf8 tools/deploy_flashlight_nofade_test.py --variant gain2x rollback
```

该命令恢复本轮替换前的独立测试 VPK，不会回退 C 的 190 贴图或 DLL。回滚预检可使用同一命令将 `rollback` 换为 `rollback-preview`，不修改游戏文件。

离线恢复副本命令（只写项目输出目录）：

```text
python -X utf8 tools/build_flashlight_gain_test.py --rollback-copy
```
