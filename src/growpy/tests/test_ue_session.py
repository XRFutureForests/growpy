"""Tests for growpy.tools.ue_session (no editor: every editor call is a fake)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from growpy.tools import ue_session
from growpy.tools.ue_session import (
    ENV_ENGINE,
    ENV_LOCK_DIR,
    ENV_PROJECT,
    LockRefused,
    Runner,
    Step,
    editor_lock,
    parse_args,
    restore_guard,
    run_steps,
    wait_for_file,
    wait_ready,
    zen_hung,
)


class FakeClock:
    """``clock`` and ``sleep`` sharing one fake time line."""

    def __init__(self):
        self.now = 0.0

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


@pytest.fixture
def paths(tmp_path):
    project = tmp_path / "proj" / "Twin.uproject"
    project.parent.mkdir()
    project.write_text("{}")
    engine = tmp_path / "UnrealEditor.exe"
    engine.write_text("")
    return {"project": project, "engine": engine, "locks": tmp_path / "locks"}


def _env(paths, **extra):
    env = {ENV_PROJECT: str(paths["project"]), ENV_ENGINE: str(paths["engine"])}
    env.update(extra)
    return env


class TestArguments:
    def test_the_environment_supplies_the_paths(self, paths):
        args = parse_args([], env=_env(paths, **{ENV_LOCK_DIR: str(paths["locks"])}))
        assert (args.project, args.engine, args.lock_dir) == (
            paths["project"],
            paths["engine"],
            paths["locks"],
        )
        assert (args.commit_limit, args.zen_timeout, args.steps) == (85.0, 360.0, ())
        assert args.editor_log == paths["project"].parent / "Saved/Logs/Twin.log"

    def test_arguments_beat_the_environment(self, paths, tmp_path):
        other = tmp_path / "Other.uproject"
        other.write_text("{}")
        args = parse_args(["--project", str(other)], env=_env(paths))
        assert args.project == other

    @pytest.mark.parametrize(
        ("drop", "argv", "match"),
        [
            (ENV_PROJECT, [], ENV_PROJECT),
            (ENV_ENGINE, [], ENV_ENGINE),
            (None, ["--lock", "slot"], ENV_LOCK_DIR),
        ],
    )
    def test_a_missing_path_is_a_clear_error(self, paths, capsys, drop, argv, match):
        env = _env(paths)
        env.pop(drop, None)
        with pytest.raises(SystemExit):
            parse_args(argv, env=env)
        assert match in capsys.readouterr().err

    def test_a_path_that_does_not_exist_is_refused(self, paths, capsys):
        with pytest.raises(SystemExit):
            parse_args(["--engine", "nope.exe"], env=_env(paths))
        assert "UnrealEditor.exe" in capsys.readouterr().err

    def test_steps_keep_their_command_line_order(self, paths):
        argv = [
            "--run", "a.py",
            "--export", "/Game/G/PVG_1",
            "--run-until-done", "t.py", "done.json", "600",
            "--run", "b.py", "30",
        ]  # fmt: skip
        args = parse_args(argv, env=_env(paths))
        assert args.steps == (
            Step("run", "a.py", 1500.0),
            Step("export", "/Game/G/PVG_1", 0.0),
            Step("until", "t.py", 600.0, Path("done.json")),
            Step("run", "b.py", 30.0),
        )

    @pytest.mark.parametrize(
        "argv",
        [
            ["--run", "a.py", "1", "2"],
            ["--run-until-done", "t.py"],
            ["--run", "a.py", "x"],
        ],
    )
    def test_malformed_steps_are_refused(self, paths, argv):
        with pytest.raises(SystemExit):
            parse_args(argv, env=_env(paths))


class TestLock:
    def test_acquire_writes_the_purpose_and_always_releases(self, tmp_path):
        locks = tmp_path / "locks"
        with editor_lock(
            locks, "slot", "E124 fill\nsecond line", lambda: 0, settle=0
        ) as p:
            assert p.read_text() == "E124 fill\n"
        assert list(locks.iterdir()) == []
        with pytest.raises(ZeroDivisionError):
            with editor_lock(locks, "slot", "", lambda: 0, settle=0):
                1 / 0  # noqa: B018
        assert list(locks.iterdir()) == []

    def test_another_lock_or_the_own_name_refuses(self, tmp_path):
        locks = tmp_path / "locks"
        locks.mkdir()
        for held in ("other.lock", "slot.lock"):
            (locks / held).write_text("x")
            with pytest.raises(LockRefused, match=held):
                with editor_lock(locks, "slot", "", lambda: 0, settle=0):
                    pass
            assert (locks / held).exists()  # someone else's lock stays
            (locks / held).unlink()

    def test_a_name_ending_in_lock_is_not_suffixed_twice(self, tmp_path):
        locks = tmp_path / "locks"
        for name in ("slot", "slot.lock"):
            with editor_lock(locks, name, "", lambda: 0, settle=0):
                assert sorted(p.name for p in locks.iterdir()) == ["slot.lock"]
            assert not any(locks.iterdir())

    def test_a_running_editor_refuses(self, tmp_path):
        with pytest.raises(LockRefused, match="UnrealEditor"):
            with editor_lock(tmp_path / "locks", "slot", "", lambda: 1, settle=0):
                pass
        assert list((tmp_path / "locks").iterdir()) == []

    def test_a_lock_that_appears_while_settling_backs_off(self, tmp_path):
        locks = tmp_path / "locks"

        def rival(_seconds):
            (locks / "rival.lock").write_text("x")

        with pytest.raises(LockRefused, match="rival.lock"):
            with editor_lock(locks, "slot", "", lambda: 0, sleep=rival):
                pass
        assert sorted(p.name for p in locks.iterdir()) == ["rival.lock"]


class TestRestoreGuard:
    def _write(self, project, data, encoding="utf-8"):
        path = project.parent / "Saved" / "Autosaves" / "PackageRestoreData.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(json.dumps(data).encode(encoding))
        return path

    def test_restore_data_with_packages_is_set_aside(self, paths):
        path = self._write(paths["project"], {"Packages": ["/Game/A"]}, "utf-16")
        assert restore_guard(paths["project"]) == "restore data set aside: 1 package(s)"
        assert not path.exists()
        assert [p.name.split(".aside_")[0] for p in path.parent.iterdir()] == [
            path.name
        ]

    def test_clean_or_absent_restore_data_stays(self, paths):
        assert restore_guard(paths["project"]) == "restore data absent"
        path = self._write(paths["project"], {"RestoreEnabled": False, "Packages": []})
        assert restore_guard(paths["project"]) == "restore data clean"
        assert path.exists()


ZEN_LOG = (
    "[2026.11.19-09.00.01:000][  0]LogInit: Display: Starting\n"
    "[2026.11.19-09.00.02:000][  0]LogZenServiceInstance: Display: "
    "Waiting for ZenServer to be ready...\n"
)


class TestZenHang:
    def test_the_decision_on_canned_log_text(self):
        assert zen_hung(ZEN_LOG, 360.0, 360.0)
        assert zen_hung(ZEN_LOG + "\n\n", 400.0, 360.0)  # trailing blank lines
        assert not zen_hung(ZEN_LOG, 359.0, 360.0)  # not yet
        moved_on = ZEN_LOG + "[...]LogInit: Display: Engine is initialized.\n"
        assert not zen_hung(moved_on, 900.0, 360.0)
        assert not zen_hung("", 900.0, 360.0)

    def test_wait_ready_reports_zen_after_the_timeout(self):
        fake = FakeClock()
        state = wait_ready(
            lambda: False,
            lambda: ZEN_LOG,
            ready_timeout=1800,
            zen_timeout=360,
            clock=fake.clock,
            sleep=fake.sleep,
        )
        assert (state, fake.now) == ("zen", 360.0)

    def test_wait_ready_answers_ready_or_times_out(self):
        fake = FakeClock()
        answers = iter([False, False, True])
        state = wait_ready(
            lambda: next(answers),
            lambda: "LogInit: still loading",
            ready_timeout=1800,
            zen_timeout=360,
            clock=fake.clock,
            sleep=fake.sleep,
        )
        assert (state, fake.now) == ("ready", 40.0)
        fake = FakeClock()
        state = wait_ready(
            lambda: False,
            lambda: "LogInit: still loading",
            ready_timeout=100,
            zen_timeout=360,
            clock=fake.clock,
            sleep=fake.sleep,
        )
        assert state == "timeout"


class TestDoneFile:
    def test_the_wait_ends_when_the_file_appears(self, tmp_path):
        done = tmp_path / "done.json"
        fake = FakeClock()

        def sleep(seconds):
            fake.sleep(seconds)
            if fake.now >= 30:
                done.write_text("{}")

        assert wait_for_file(done, 60, clock=fake.clock, sleep=sleep)
        assert fake.now == 30.0

    def test_the_wait_times_out(self, tmp_path):
        fake = FakeClock()
        assert not wait_for_file(
            tmp_path / "done.json", 60, clock=fake.clock, sleep=fake.sleep
        )
        assert fake.now == 60.0


class TestSteps:
    @staticmethod
    def _runner(calls, fail=()):
        def run(target, timeout):
            calls.append(("run", target, timeout))
            return {
                "success": target not in fail,
                "output": [{"output": f"{target} ok"}],
            }

        def export(graphs, log):
            calls.append(("export", tuple(graphs)))
            return True

        def wait_file(done, timeout):
            calls.append(("wait", done.name, timeout))
            return True

        return Runner(run=run, export=export, wait_file=wait_file)

    def test_steps_run_in_order_and_adjacent_exports_go_together(self, tmp_path):
        done = tmp_path / "done.json"
        done.write_text("stale")
        steps = (
            Step("run", "build.py", 1500.0),
            Step("export", "/G/PVG_1", 0.0),
            Step("export", "/G/PVG_2", 0.0),
            Step("until", "tick.py", 600.0, done),
            Step("export", "/G/PVG_3", 0.0),
        )
        calls = []
        assert run_steps(steps, tmp_path / "x.log", self._runner(calls))
        assert calls == [
            ("run", "build.py", 1500.0),
            ("export", ("/G/PVG_1", "/G/PVG_2")),
            ("run", "tick.py", 120.0),
            ("wait", "done.json", 600.0),
            ("export", ("/G/PVG_3",)),
        ]
        assert not done.exists()  # the stale done file was removed before the run

    def test_the_first_failure_stops_the_steps(self, tmp_path, capsys):
        calls = []
        steps = (Step("run", "a.py", 10.0), Step("export", "/G/PVG_1", 0.0))
        assert not run_steps(
            steps, tmp_path / "x.log", self._runner(calls, fail={"a.py"})
        )
        assert calls == [("run", "a.py", 10.0)]
        assert "FAILED" in capsys.readouterr().out


def test_it_never_kills_by_image_name():
    source = Path(ue_session.__file__).read_text(encoding="utf-8")
    assert "taskkill" not in source.lower() and "/IM" not in source


class TestCommitGuard:
    def test_it_kills_only_its_pid_above_the_limit(self):
        killed = []
        guard = ue_session.CommitGuard(
            4242,
            85.0,
            percent=iter([60.0, 90.0]).__next__,
            alive=lambda pid: True,
            kill=killed.append,
            poll=0.0,
        )
        guard.run()
        assert (guard.fired, killed) == (True, [4242])

    def test_it_ends_with_the_editor(self):
        guard = ue_session.CommitGuard(
            4242, 85.0, percent=lambda: 99.0, alive=lambda pid: False, kill=None
        )
        guard.run()
        assert guard.fired is False
