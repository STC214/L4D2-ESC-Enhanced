# C：聊天面板移至右下方

## 布局

聊天消息历史与输入行统一位于右下方，给底部血条、弹药等 HUD 留出空间，不调整 Evo 配置。

| 项目 | 新值（VGUI 布局单位） |
|---|---|
| 聊天面板横向位置 | `xpos=r297`，宽度 280，距右边 17 |
| 聊天面板纵向位置 | `ypos=r200`，高度 120，底部预留 80 |
| 消息历史区 | 面板内 `x=10, y=16, wide=260, tall=75` |
| 输入行 | 面板内 `x=10, y=95, wide=260, tall=20` |
| 状态标签 | 保留原位置，宽度收至 260，避免超出父面板 |

同时更新 `resource/ui/basechat.res` 和 `scripts/hudlayout.res` 的 `HudChat` 根设置，避免两处位置不一致。原聊天输入行的静态 `y=395` 超出原 100 高的父面板，本轮一并规整到父面板内；保留聊天字体、历史区高度、颜色和其他行为设置。

`r` 表示从右侧或底部计算的锚点，不是固定屏幕坐标。有限布局模型覆盖 640×480、1280×720、1920×1080、2560×1440、3440×1440、3840×2160；这些是资源布局校验，不等于游戏截图验收。

## 成品与验证

- 固定 VPK：`dist/【00】C_ESC_LED_血条和速度_TUMTaRA.vpk`。
- 两件套包：`dist/C_session_release.zip`；配套 DLL 保持 1.1.0，不因本轮聊天布局改变。
- 相对上一成品，只有上述两个聊天资源改变；其余 **220 个成员逐字节保留**。
- 本轮差异：`reports/c_chat_bottom_right/chat.patch`。
- 完整审查：`reports/c_chat_bottom_right/verification.json`，覆盖两轮全成员审核、43 项 C 回归、13 项部署夹具、补丁重放、回滚及确定性构建。
- 实际安装与备份记录：`reports/c_session_deploy/verification.json` 和同目录 `transaction.json`，以记录中的目标哈希判定安装版本。

构建入口沿用：

```text
python -X utf8 tools/build_c_mod.py --width 1280 --height 720
python -X utf8 tools/full_review.py
python -X utf8 tools/c_chat_layout.py verify
```

本轮恢复入口：

```text
python -X utf8 tools/c_chat_layout.py rollback-copy
```

该命令把修改前的 VPK 恢复并校验到 `dist/rollback_chat_bottom_right/`，不直接覆盖游戏。退出游戏后可用它替换安装的 C；本轮没有更改 DLL，恢复聊天位置不需要降级 DLL。游戏部署工具另保留实际安装前的事务备份。

## 仍需游戏内检查

- 打开全局/队伍聊天，确认历史消息和输入行都在右下方且文字完整。
- 检查底部弹药、血条、速度表及其他 HUD 是否仍有遮挡。
- Evo 默认左上小地图与新聊天区域在有限模型中分离；真实渲染、引擎动态布局和其他 HUD MOD 的影响仍需实测。
- 改变分辨率、窗口模式或聊天字体后重新查看。
