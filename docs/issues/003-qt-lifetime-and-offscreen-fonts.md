# Qt 自动测试中的对象生命周期与离屏字体

## 现象
加入真实 TCP 测试后，单项测试通过，连续运行却在处理事件时发生 Python Aborted。离屏预览中的中文和英文同时显示为方框。

## 原因与修复
- Qt 信号回调与 Python 对象形成引用环。测试结束仅停止定时器、不明确销毁窗口，会使对象留到之后的垃圾回收阶段；网络线程可能触发回收，导致 GUI 对象在错误线程释放。关闭服务时对窗口、定时器和 TCP 服务调用 `deleteLater()`，并在测试主线程处理 DeferredDelete 事件。公共 QApplication 与服务 fixture 统一放入 conftest。
- Windows 的 Qt offscreen 插件没有枚举系统字体，`QFontDatabase.families()` 返回空列表。预览脚本在此情况下显式载入系统微软雅黑字体；实际桌面运行使用 Qt Windows 平台插件，不改动用户字体设置。

## 验证
连续运行消息与畸形 IPC 测试通过；重新生成预览并人工检查，中文、英文、多行和三种消息颜色均可见。
