# 全局光标能力与跨平台边界

## 问题
Qt 的应用覆盖光标只影响自身窗口，不能实现规格所需的全桌面提示。Wayland 普通客户端没有统一的全局定位、替换光标与任意定位浮层接口。

## 解决方法
- Windows 用 `LoadCursorW` 读取 13 类标准系统光标，`CopyImage` 按原尺寸缩放，`SetSystemCursor` 替换。复制原始句柄后再操作，避免连续消息发生 5×5 倍放大。
- macOS 使用 Cocoa 获取当前光标图像，以 Quartz 隐藏真实光标，Qt 绘制其放大图像。
- Linux X11 使用 XFixes 获取当前图像与热点，隐藏原光标，由 Qt 绘制放大图像；关闭 X11 连接释放隐藏请求。
- Wayland 在 CLI 层明确报错，不用 XWayland 冒充完整支持。后续若要支持，需要 GNOME/KDE 等合成器专用方案。

## 当前限制
- Windows 面向标准系统光标，应用自定义光标与独占全屏程序不能保证有效；动画光标的所有帧不保证完整保留。当前验证的是默认系统方案。
- macOS/X11 在一次提示期间显示触发时的图像快照，不跟随应用的光标形状变化。
- macOS/X11 后端已编写，当前 Windows 环境不能证明实机效果、权限与全屏行为。

## 参考
- https://doc.qt.io/qt-6/qguiapplication.html#setOverrideCursor
- https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setsystemcursor
- https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-copyimage
- https://wayland.freedesktop.org/docs/book/Protocol.html
