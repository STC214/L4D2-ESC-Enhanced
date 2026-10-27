# 独立测试：关闭手电射程末端淡出（0.1-test）

> 历史独立测试记录：淡出抑制及后续 RGB 2 倍版本已整合进 C 1.3.0。使用新版 C 时停用独立测试包，当前安装方式见 [C 使用说明](C使用说明.md)。以下保留初期测试原记录。

## 测试目标与边界

这是独立于 C 的实验模组。只替换 `shaders/fxc/flashlight_ps30.vcs` 中经过识别的射程末端淡出乘数，将该乘数换成已有常量 1。保留距离项、射程边界、阴影、材质入射角和贴图。

不包含 LED、VMT、CFG、DLL，不改 C 的光圈 165、射程 3000 和其他默认项。仅覆盖这一个 ps_3_0 shader 文件，不承诺眼睛、牙齿或其他独立着色器也同时生效。

**当前状态：文件构建及自动化验证通过；未部署，未验证真实游戏加载及显示效果。**

## 产物

目录：`dist/flashlight_nofade_test/`。

- `C_flashlight_nofade_TEST.vpk`：独立实验包。
- `C_flashlight_nofade_loose_TEST.zip`：同一修改版 shader 的松散文件包，路径为 `left4dead2/shaders/fxc/flashlight_ps30.vcs`。
- `baseline_control_DO_NOT_ENABLE_WITH_TEST.vpk`：原始 shader 对照包，**不要与实验包同时启用**。
- `original/shaders/fxc/flashlight_ps30.vcs`：按 SHA-256 校验的原件备份。
- `rollback_copy/shaders/fxc/flashlight_ps30.vcs`：已执行恢复和重读校验的原件副本。

## 试用顺序

1. 退出游戏，保留现有 C 及其 DLL 不变。
2. 先只将 `C_flashlight_nofade_TEST.vpk` 放入 `left4dead2/addons/`，启用它；不要同时放入原始对照包。
3. 重启游戏，进入同一地图、同一位置，以相同光圈、射程和画面设置对照远处物体。需观察射程后 40% 的区域；默认射程 3000 时，近处 1800 以内可能没有区别。
4. 记录截图和参数，区分曝光适应变化与手电实际变化。射程边界依然存在，不是无限距离光源。
5. 如果没有变化，先不要认定补丁无效：附加内容 VPK 的 shader 搜索优先级和实际选择的 shader 组合尚待确认。

若需要进一步测试松散覆盖，先停用 VPK 实验包，检查并备份实际游戏目录中同路径文件，再将松散包解压到游戏根目录。**两种安装形式只选一种。** 若已有同名文件，应先确认其来源，不盲目覆盖。

该安装路径是否优先于其他平台/模组仍需实际验证；本实验没有修改 `hl2` 内原始文件，也没有自动清理 shader 缓存或更改其他平台。

## 卸载与恢复

- VPK 方式：退出游戏，停用并将实验 VPK 移出 `addons`，再重启。
- 松散方式：退出游戏，只移出本次放入的同路径文件；若安装前已有同名文件，恢复自己的备份。不要删除整个 shaders 目录，不要动 `hl2/shaders` 内的原件。
- 恢复副本命令（只在项目输出目录生成副本，不改游戏）：

```text
python -X utf8 tools/build_flashlight_nofade_test.py --rollback-copy
```

## 验证范围

```text
python -X utf8 tools/build_flashlight_nofade_test.py
python -X utf8 tools/verify_flashlight_nofade_test.py
```

基线 SHA-256：`cd9b779c792d9391c82da548d155efe80801812fda0f41585725bc766cd3829f`。

检查覆盖该文件的 1,416 个唯一静态组合块、2,832 个独立程序。每个程序仅变化一个源操作数字；指令长度和 CTAB 反射不变，静态 ID 和别名表保留，压缩块及文件偏移重新构建。所有修改程序均通过 `D3DDisassemble`，代表组合保留 `fxc /dumpbin` 原样前后输出。

记录：`reports/flashlight_nofade_test/verification.json`、`independent_verification.json`；补丁操作数清单在前者的 `patches` 字段。

这只能证明文件与已检查的字节码结构正确，不等于 GPU 已执行该文件，也不等于所有地图/平台/材质兼容。

## 工坊 962925054 的检查结论

原件：`originals/LIGHT_962925054.vpk`，SHA-256：`0bc2fb5daeeef1a60d744237088c75478ce35367e6fb8dea52600789a9bd32a0`。

包内仅有 `materials/effects/flashlight001.vtf` 和 `addoninfo.txt`。贴图为 512×512 DXT5、10 层 mip，RGB 全图加权均值约 183.40/255、近纯白像素约 64.97%、Alpha 全为 255。它没有替换 shader 或距离参数，因此并未取消游戏本身的射程末端淡出；其亮度优势主要在贴图亮区分布，不能称为“无衰减手电”。

本次没有把这个工坊贴图合入 C，也未改变游戏当前已部署的 Glare 替换版。
