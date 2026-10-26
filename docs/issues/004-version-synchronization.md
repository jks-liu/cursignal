# 升版时三处版本与 uv 锁文件同步

## 问题
项目版本分别出现在 pyproject.toml、运行时 __version__、uv.lock 中。只更新一个文件会让 CLI 输出和构建元数据不一致。全局替换版本字符串可能修改其他依赖；README 固定 wheel 文件名也会在升版后过时。

## 解决方法
版本脚本先解析 TOML 和 Python AST，确认三处一致；只修改 project 表、__version__ 赋值和 source 为本地 editable 的 cursignal 条目。保留其他依赖版本、哈希、注释和换行，不引入 TOML 序列化依赖。写入失败时恢复已修改文件；构建失败时保留已同步版本并明确报错。

使用 `--no-project` 执行，保证 current 本身不写文件，也避免 uv 在脚本执行前同步项目环境。README 用版本占位符描述 wheel 文件名。

## 验证
脚本测试覆盖升版级别、精确版本、只读查询、版本不一致、非法参数、写入回滚与构建失败。临时副本升版、真实构建与 `uv lock --check --offline` 已通过，证明仅更新本项目版本不会使现有锁文件失效。
