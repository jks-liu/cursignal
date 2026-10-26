# 辅助脚本

在仓库根目录执行，依赖由 `uv sync` 安装。

- `uv run python tools/preview.py`：离屏渲染消息浮层到 `artifacts/overlay-preview.png`；不修改系统光标。可传入输出路径。
- `uv run python tools/smoke_windows.py`：Windows 桌面端到端验证。会短暂放大光标、移动鼠标几个像素，并在结束时恢复位置。验证并发启动、5 倍尺寸、渐变、动画期间追加、GUI 崩溃恢复与重新启动。已有后台进程时拒绝运行，先执行 `uv run cursignal --stop`。测试时请勿操作鼠标，以免提前触发动画。结果写入 `artifacts/windows-smoke.json`。

通常验证使用 `uv run pytest`，无需实际改变桌面。原生接口或进程生命周期修改后再运行桌面脚本。

## 版本更新

脚本仅依赖 Python 3.11+ 标准库。建议使用 `--no-project`，避免版本管理操作触发项目环境同步或 Qt 安装；也可以直接执行 `python tools/version_bump.py`。

```powershell
# 默认 patch：0.1.0 -> 0.1.1
uv run --no-project python tools/version_bump.py

# 升版后构建 wheel 和 sdist（输出到 dist/）
uv run --no-project python tools/version_bump.py patch --build

# 明确选择升级级别
uv run --no-project python tools/version_bump.py minor
uv run --no-project python tools/version_bump.py major

# 设置精确版本
uv run --no-project python tools/version_bump.py 1.0.0

# 明确跳过构建（默认行为）
uv run --no-project python tools/version_bump.py patch --no-build

# 只读查询，并确认三处版本一致
uv run --no-project python tools/version_bump.py current
```

同步位置：`pyproject.toml` 的项目版本、`src/cursignal/__init__.py` 的 `__version__`、`uv.lock` 中本地 cursignal 条目的版本。其他依赖版本、哈希、注释和换行不变；默认操作不联网、不重新解析依赖。

规则：

- 支持稳定版本 `X.Y.Z`，不接受 `v` 前缀、前导零、预发布或构建后缀。
- patch 增加第三段；minor 增加第二段并清零第三段；major 增加第一段并清零后两段。
- 精确版本可以等于当前版本，也可以设置为较低版本。
- 原有三处版本不一致时，查询和更新都报错，不自动猜测正确版本。
- `current --build` 和 `--build --no-build` 是参数冲突。
- 更新前完成格式校验，单文件使用临时文件替换；普通写入失败时恢复已写入的文件。该机制不保证断电或进程被强杀时多文件事务的原子性，下一次执行会检查版本一致性。
- 构建在同步成功后执行。构建失败返回非零退出码，但保留已同步的新版本；修复后运行 `uv build` 重试，`dist/` 可能留有部分构建结果。
- 不自动提交 Git、不打 tag、不发布 PyPI。脚本根据自身位置定位仓库，与启动时的工作目录无关。
