"""Synchronize release versions without installing project dependencies.

Usage: uv run --no-project python tools/version_bump.py [patch|minor|major|X.Y.Z|current]
Add --build to run `uv build` after updating; --no-build is the default.
Only stable X.Y.Z versions are accepted. Run from any working directory.
"""

import argparse
import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", re.ASCII)
FILES = ("pyproject.toml", "src/cursignal/__init__.py", "uv.lock")


def require_version(value: str) -> str:
    if not isinstance(value, str) or not VERSION.fullmatch(value):
        raise ValueError(f"版本必须是 X.Y.Z 格式的非负整数，不支持前导零或预发布后缀：{value!r}")
    return value


def next_version(current: str, level: str) -> str:
    major, minor, patch = map(int, require_version(current).split("."))
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    if level == "patch":
        return f"{major}.{minor}.{patch + 1}"
    return require_version(level)


def versions(contents: dict[str, bytes]) -> list[str]:
    project = tomllib.loads(contents[FILES[0]].decode("utf-8"))["project"]
    tree = ast.parse(contents[FILES[1]].decode("utf-8"))
    runtime = [
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets
        )
    ]
    lock = tomllib.loads(contents[FILES[2]].decode("utf-8"))
    packages = [
        entry
        for entry in lock["package"]
        if entry["name"] == project["name"] and entry.get("source") == {"editable": "."}
    ]
    if len(runtime) != 1 or len(packages) != 1:
        raise ValueError("必须恰好有一个 __version__ 和一个本地项目锁文件条目")
    return [require_version(v) for v in (project["version"], runtime[0], packages[0]["version"])]


def replace_assignment(text: str, key: str, target: str) -> str:
    # Preserve comments, quotes, whitespace and line endings; do not rewrite entire TOML files.
    pattern = rf"(?m)^([ \t]*{re.escape(key)}[ \t]*=[ \t]*)([\"'])([^\r\n]*?)(\2)([ \t]*(?:#[^\r\n]*)?\r?)$"
    updated, count = re.subn(
        pattern,
        lambda match: f"{match[1]}{match[2]}{target}{match[4]}{match[5]}",
        text,
    )
    if count != 1:
        raise ValueError(f"无法唯一定位 {key} 的单行字符串赋值；未修改文件")
    return updated


def updated_contents(original: dict[str, bytes], target: str) -> dict[str, bytes]:
    result = {}
    project_text = original[FILES[0]].decode("utf-8")
    sections = re.split(r"(?m)(?=^\[)", project_text)
    count = 0
    for index, section in enumerate(sections):
        if re.match(r"\[project\][ \t]*(?:#[^\r\n]*)?\r?\n", section):
            sections[index] = replace_assignment(section, "version", target)
            count += 1
    if count != 1:
        raise ValueError("无法唯一定位 [project] 表；未修改文件")
    result[FILES[0]] = "".join(sections).encode("utf-8")
    result[FILES[1]] = replace_assignment(
        original[FILES[1]].decode("utf-8"), "__version__", target
    ).encode("utf-8")
    name = tomllib.loads(project_text)["project"]["name"]
    sections = re.split(r"(?m)(?=^\[\[package\]\])", original[FILES[2]].decode("utf-8"))
    count = 0
    for index, section in enumerate(sections):
        if not section.startswith("[[package]]"):
            continue
        package = tomllib.loads(section)["package"][0]
        if package["name"] == name and package.get("source") == {"editable": "."}:
            sections[index] = replace_assignment(section, "version", target)
            count += 1
    if count != 1:
        raise ValueError("无法唯一定位本项目的锁文件版本；未修改文件")
    result[FILES[2]] = "".join(sections).encode("utf-8")
    if versions(result) != [target] * 3:
        raise ValueError("更新后的版本校验失败；未修改文件")
    return result


def atomic_write(path: Path, content: bytes) -> None:
    # Stage in the same directory so os.replace works across platforms/volumes.
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
        shutil.copymode(path, temporary)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def save_versions(root: Path, original: dict[str, bytes], updated: dict[str, bytes]) -> None:
    written = []
    try:
        for filename in FILES:
            if updated[filename] != original[filename]:
                atomic_write(root / filename, updated[filename])
                written.append(filename)
    except (OSError, KeyboardInterrupt) as error:
        failures = []
        for filename in reversed(written):
            try:
                atomic_write(root / filename, original[filename])
            except OSError:
                failures.append(filename)
        if failures:
            raise RuntimeError(
                f"写入失败且无法恢复这些文件，请手动检查：{', '.join(failures)}"
            ) from error
        raise


def main(argv: list[str] | None = None, *, root: Path | None = None) -> int:
    parser = argparse.ArgumentParser(description="同步项目、运行时及 uv.lock 版本（默认 patch）。")
    parser.add_argument("level", nargs="?", default="patch", help="patch/minor/major/X.Y.Z/current")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--build", action="store_true", help="升版后使用 uv build 构建 wheel 和 sdist"
    )
    group.add_argument("--no-build", action="store_true", help="只更新版本，不构建（默认）")
    args = parser.parse_args(argv)
    if args.level == "current" and args.build:
        parser.error("current 为只读查询，不能与 --build 同时使用")
    root = root or Path(__file__).resolve().parents[1]
    try:
        original = {filename: (root / filename).read_bytes() for filename in FILES}
        found = versions(original)
        if len(set(found)) != 1:
            detail = ", ".join(f"{filename}={value}" for filename, value in zip(FILES, found))
            raise ValueError(f"版本不同步，请先修正：{detail}")
        current = found[0]
        if args.level == "current":
            print(current)
            return 0
        target = next_version(current, args.level)
        uv = shutil.which("uv") if args.build else None
        if args.build and uv is None:
            raise ValueError("构建需要 uv，请先安装 uv；未修改文件")
        save_versions(root, original, updated_contents(original, target))
        print(f"{current} -> {target}", flush=True)
        if args.build:
            try:
                subprocess.run([uv, "build"], cwd=root, check=True)
            except (OSError, subprocess.CalledProcessError) as error:
                raise RuntimeError(
                    f"构建失败；版本已同步为 {target}，修复构建问题后可运行 uv build 重试"
                ) from error
        return 0
    except (OSError, ValueError, KeyError, SyntaxError, RuntimeError) as error:
        print(f"version-bump: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
