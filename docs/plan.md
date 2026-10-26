# cursignal 实施计划与进度

## 当前任务：版本更新脚本
- 需求：默认 patch，支持 minor/major、精确 X.Y.Z、--build/--no-build 和只读 current。
- 实现：tools/version_bump.py，使用 Python 标准库，同步 pyproject.toml、运行时 __version__、uv.lock 中本项目的版本；默认不构建。
- 进度：已完成脚本、使用说明与 19 项针对性测试。临时副本升版到 0.1.1 后真实构建、wheel 元数据/运行时版本、sdist、uv 离线锁文件检查均通过。
- 交接：实际仓库版本保持 0.1.0；用 `uv run --no-project python tools/version_bump.py current` 查询。默认 patch；构建失败保留已同步的新版本，可直接 `uv build` 重试。

## 目标与已确定方案
- 用户已选择 uvx；实现 `cursignal "message"`，光标放大 5 倍，移动后在 3 秒内还原并淡出消息；新消息使用不同颜色追加。
- Python + PySide6 Essentials（Qt 官方基础模块包），命令行通过本地 IPC 连接单一 GUI 进程。
- Windows 使用原生系统光标缩放，并由独立进程持有原始光标，GUI 意外退出后恢复。
- macOS 和 Linux X11 使用原始光标图像与透明浮层，显示期间隐藏系统光标。Wayland 需要合成器专用接口，明确报错，不能声称通用支持。

## 当前进度
- [x] 阅读规格、确认 uvx 技术路线、查阅系统接口文档。
- [x] CLI、单实例通信、状态机、浮层与平台后端。
- [x] 自动测试、Windows 原生接口与端到端验证、构建验证。
- [x] 使用说明、平台边界、问题与经验记录。

## 验证结果与交接
- 自动测试覆盖状态机、参数、服务清理、真实 TCP 认证与畸形数据；ruff 与构建通过。最终命令和结果见 README 与 docs/changes.md。
- `tools/smoke_windows.py` 两次通过：三个并发冷启动、13 种光标精确 5 倍尺寸、移动后渐变、动画中追加、正常退出、GUI 强杀恢复、崩溃后重启。证据在 `artifacts/windows-smoke.json`。
- `uvx --from . cursignal` 已实际发送消息、查询状态并正常停止。离屏消息预览已检查中文、多行和颜色。
- 当前只有 Windows 执行环境；macOS/X11 后端待实机验证。Wayland 暂不支持。Windows 自定义光标、动画光标的完整帧恢复、多屏混合 DPI 和独占全屏属于已注明的边界，不能宣称已验证。
- 仓库尚未发布 PyPI；本地用 `uv run cursignal` 或 `uvx --from . cursignal`，不能把线上同名包当成本项目。

## 后续验证入口
- `uv run pytest -q`；`uv run ruff check .`；`uv run ruff format --check .`；`uv build`。
- 原生桌面验证见 tools/README.md。测试完毕停止后台进程，不遗留提示。
- 如继续补齐平台支持，先在 macOS/X11 实机验证隐藏/恢复、点击穿透、多显示器和崩溃行为，再更新支持矩阵；Wayland 需单独设计合成器扩展。
