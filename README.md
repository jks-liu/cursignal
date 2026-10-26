# cursignal

通过放大鼠标光标并显示文字，提示命令或任务已完成。Python 3.11+。

开发与本地运行（需先安装 uv）：

```powershell
uv sync
uv run cursignal "任务完成"
uv run cursignal "另一个任务完成"
uv run cursignal --status
uv run cursignal --stop
```

在仓库目录使用 uvx：

```powershell
uvx --from . cursignal "任务完成"
```

尚未发布到 PyPI，当前不要直接运行 `uvx cursignal`，以免执行无关同名包。

如果需要在任意目录直接使用 `cursignal`，在仓库根目录执行：

```powershell
uv tool install .
cursignal "任务完成"
```

## 行为

- 命令发送成功即返回，不占用当前终端。首次调用启动桌面进程，后续调用复用同一进程。
- 光标宽、高分别放大到原来的 5 倍，文字显示在其下方；靠近屏幕下边缘时移到上方。
- 鼠标静止时一直显示。首次检测到移动后，在 3 秒内平滑缩小光标、淡出文字。
- 新消息按到达顺序追加，使用六种循环颜色，相邻消息颜色不同。动画期间收到新消息时，全部消息恢复显示，光标重新放大并等待下一次移动。
- 浮层不获取键盘焦点，并允许鼠标点击穿透。支持中文、换行与长文本自动折行，内容按纯文本显示。
- 单条最多 4096 字符，最多积累 128 条消息。屏幕放不下时优先显示最近的完整消息卡片；单条超出屏幕高度时裁切。消息不会保存到磁盘。
- 消息消失后空闲 60 秒自动退出。`--stop` 可随时清除提示、恢复光标并退出；`--status` 输出 JSON 状态，便于脚本检查。

## 平台支持与限制

| 平台 | 实现 | 验证情况 |
| --- | --- | --- |
| Windows | 原生缩放 13 类标准系统光标；独立进程负责恢复 | 本机已通过并发、动画、GUI 强杀恢复、uvx 安装运行验证 |
| macOS | Cocoa 获取当前光标图像，Quartz 隐藏原光标，Qt 绘制放大图像 | 后端已实现，待 macOS 实机验证 |
| Linux X11 | XFixes 获取并隐藏原光标，Qt 绘制放大图像 | 后端已实现，待 X11 实机验证 |
| Linux Wayland | 没有通用的全局光标实现，启动时明确报错 | 暂不支持；请使用 X11 会话 |

需要实际的图形桌面会话。Windows 的应用自定义光标、动画光标完整帧恢复、游戏独占全屏和安全桌面不保证支持；macOS/X11 使用触发时的光标图像快照，提示期间不会随应用切换光标形状。多屏混合 DPI 与 macOS 全屏 Space 仍需实机验证。

Windows 的恢复进程能处理 GUI 崩溃或被强制结束。如果把整个进程树（包括恢复进程）一起强杀，需在系统鼠标设置中重新应用光标方案。

Linux 需要系统的 X11、XFixes 4+ 和 Qt xcb 平台依赖。在 Debian/Ubuntu 桌面上，缺少依赖时可安装：

```sh
sudo apt install libx11-6 libxfixes3 libxcb-cursor0 libxkbcommon-x11-0 libegl1 libopengl0
```

macOS 的 PyObjC 依赖会按平台自动安装。Qt 自带二进制随 Python 包安装，首次下载相对较大。

## 开发与验证

```powershell
uv sync --locked
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv build
```

自动测试使用离屏 Qt 和模拟平台后端，不修改真实光标。原生 Windows 验证和浮层预览见 [tools/README.md](tools/README.md)。构建结果在 `dist/`；使用 `uvx --from ./dist/cursignal-<版本>-py3-none-any.whl cursignal --version` 可检查 wheel 入口，请将 `<版本>` 替换为实际版本号。

版本更新（默认 patch，同步项目、运行时和锁文件版本）：

```powershell
uv run --no-project python tools/version_bump.py
uv run --no-project python tools/version_bump.py minor --build
uv run --no-project python tools/version_bump.py current
```

精确版本、major、`--no-build` 和失败处理详见 [版本更新脚本说明](tools/README.md#版本更新)。

运行状态、令牌和最近一次启动的日志位于：

- Windows：`%LOCALAPPDATA%/cursignal/`
- macOS：`~/Library/Caches/cursignal/`
- Linux：`$XDG_RUNTIME_DIR/cursignal/`，没有该变量时为 `~/.cache/cursignal/`

启动失败优先检查该目录中的 `server.log`。IPC 仅监听 loopback，使用随机令牌；非 Windows 平台将状态目录权限限制为当前用户。

实现交接见 [docs/plan.md](docs/plan.md)，关键修改见 [docs/changes.md](docs/changes.md)，问题与经验分别保存在 `docs/issues/`、`docs/lessons/`。
