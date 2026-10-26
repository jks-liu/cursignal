import importlib.util
from pathlib import Path
from subprocess import CalledProcessError

import pytest

REPOSITORY = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("version_bump", REPOSITORY / "tools/version_bump.py")
bump = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bump)


@pytest.fixture
def project(tmp_path):
    for filename in bump.FILES:
        destination = tmp_path / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((REPOSITORY / filename).read_bytes())
    return tmp_path


def snapshot(project):
    return {filename: (project / filename).read_bytes() for filename in bump.FILES}


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], "0.1.1"),
        (["patch"], "0.1.1"),
        (["minor"], "0.2.0"),
        (["major"], "1.0.0"),
        (["1.2.3"], "1.2.3"),
        (["patch", "--no-build"], "0.1.1"),
    ],
)
def test_synchronized_bump_without_build(project, monkeypatch, args, expected):
    # Normalize the fixture so these cases remain valid after real releases.
    original = snapshot(project)
    bump.save_versions(project, original, bump.updated_contents(original, "0.1.0"))
    before = snapshot(project)

    def unexpected(*args, **kwargs):
        pytest.fail("Default bump must not spawn uv or build anything")

    monkeypatch.setattr(bump.subprocess, "run", unexpected)
    assert bump.main(args, root=project) == 0
    after = snapshot(project)
    assert bump.versions(after) == [expected] * 3
    # Other package versions, hashes, comments and newline styles remain byte-identical.
    assert bump.updated_contents(after, "0.1.0") == before


def test_current_is_read_only(project, capsys):
    before = snapshot(project)
    times = [(project / name).stat().st_mtime_ns for name in bump.FILES]
    assert bump.main(["current"], root=project) == 0
    assert capsys.readouterr().out.strip() == bump.versions(before)[0]
    assert snapshot(project) == before
    assert [(project / name).stat().st_mtime_ns for name in bump.FILES] == times


@pytest.mark.parametrize("level", ["1.2", "v1.2.3", "01.2.3", "1.0.0rc1", "other"])
def test_invalid_version_does_not_write(project, level):
    before = snapshot(project)
    assert bump.main([level], root=project) == 1
    assert snapshot(project) == before


def test_mismatch_fails_without_modifying_files(project):
    (project / bump.FILES[1]).write_text('__version__ = "99.0.0"\n', encoding="utf-8")
    before = snapshot(project)
    assert bump.main(["current"], root=project) == 1
    assert bump.main([], root=project) == 1
    assert snapshot(project) == before


def test_failed_write_restores_prior_files(project, monkeypatch):
    before = snapshot(project)
    write = bump.atomic_write

    def failing_write(path, content):
        if path.name == "uv.lock":
            raise PermissionError("test failure")
        write(path, content)

    monkeypatch.setattr(bump, "atomic_write", failing_write)
    assert bump.main([], root=project) == 1
    assert snapshot(project) == before


def test_build_runs_after_synchronizing(project, monkeypatch):
    monkeypatch.setattr(bump.shutil, "which", lambda name: "/tools/uv")
    calls = []

    def build(command, *, cwd, check):
        assert bump.versions(snapshot(project)) == ["1.2.3"] * 3
        calls.append((command, cwd, check))

    monkeypatch.setattr(bump.subprocess, "run", build)
    assert bump.main(["1.2.3", "--build"], root=project) == 0
    assert calls == [(["/tools/uv", "build"], project, True)]


def test_build_failure_keeps_new_version_and_reports_error(project, monkeypatch, capsys):
    monkeypatch.setattr(bump.shutil, "which", lambda name: "/tools/uv")

    def build(*args, **kwargs):
        raise CalledProcessError(1, args[0])

    monkeypatch.setattr(bump.subprocess, "run", build)
    assert bump.main(["1.2.3", "--build"], root=project) == 1
    assert bump.versions(snapshot(project)) == ["1.2.3"] * 3
    assert "uv build" in capsys.readouterr().err


def test_missing_uv_does_not_bump(project, monkeypatch):
    before = snapshot(project)
    monkeypatch.setattr(bump.shutil, "which", lambda name: None)
    assert bump.main(["--build"], root=project) == 1
    assert snapshot(project) == before


@pytest.mark.parametrize("args", [["current", "--build"], ["--build", "--no-build"]])
def test_conflicting_arguments_are_rejected(project, args):
    before = snapshot(project)
    with pytest.raises(SystemExit) as error:
        bump.main(args, root=project)
    assert error.value.code == 2
    assert snapshot(project) == before
