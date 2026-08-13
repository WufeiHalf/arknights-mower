import pathlib
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import arknights_mower.solvers.base_schedule as base_schedule
import arknights_mower.utils.solver as solver_module
from arknights_mower.solvers.base_schedule import BaseSchedulerSolver
from arknights_mower.utils.config.conf import Conf
from arknights_mower.utils.recognize import Scene
from arknights_mower.utils.solver import BaseSolver


def make_conf(**kwargs) -> Conf:
    fields = dict(
        maa_rg_enable=1,
        maa_long_task_type="bf",
        maa_rg_sleep_min="0:00",
        maa_rg_sleep_max="0:00",
        maa_path="/fake/maa",
    )
    fields.update(kwargs)
    return Conf.model_construct(**fields)


class TestMaaPlanSolverBfDispatch(unittest.TestCase):
    """分派 seam：conf.BF 时 maa_plan_solver 走预检 → to_blackflow → append Custom 任务链。"""

    def _solver_with_maa(self, maa: MagicMock) -> BaseSchedulerSolver:
        solver = object.__new__(BaseSchedulerSolver)
        solver.device = MagicMock()
        solver.recog = MagicMock()
        # 让 maa_gap 等待分支生效，跳过日常 MAA 段落，聚焦大型任务分派
        solver.last_execution = {"maa": datetime.now() + timedelta(hours=1)}
        solver.tasks = [SimpleNamespace(time=datetime.now() - timedelta(minutes=5))]
        solver.drop_send = False
        solver.check_current_focus = MagicMock()
        solver.rest_after_maa = MagicMock()
        solver.maa_stop = MagicMock()
        solver.back_to_index = MagicMock()
        solver.to_blackflow = MagicMock()
        solver.initialize_maa = MagicMock(
            side_effect=lambda: setattr(solver, "MAA", maa)
        )
        return solver

    @patch.object(BaseSchedulerSolver, "__init__", lambda x: None)
    def test_bf_dispatch_prechecks_navigates_then_appends_custom_task(self):
        """验收 1+2：conf.BF 且非休眠时，预检 → to_blackflow → append Custom 任务链 → MAA.start。"""
        maa = MagicMock()
        maa.get_version.return_value = "v6.14.2"
        maa.running.side_effect = [True, False]
        solver = self._solver_with_maa(maa)
        order = []

        def fake_precheck(version, tasks_json_path):
            order.append(("precheck", version, tasks_json_path))

        def fake_to_blackflow():
            order.append(("to_blackflow",))

        with (
            patch.object(base_schedule, "send_message"),
            patch.object(base_schedule, "save_exception"),
            patch.object(base_schedule, "csleep"),
            patch.object(base_schedule.config, "conf", make_conf()),
            patch.object(
                base_schedule,
                "check_blackflow_prereqs",
                side_effect=fake_precheck,
            ) as mock_precheck,
            patch.object(solver, "to_blackflow", side_effect=fake_to_blackflow),
        ):
            solver.maa_plan_solver()

        # 预检在导航之前执行，版本来自 self.MAA.get_version()，路径来自 conf.maa_path
        self.assertEqual(order[0][0], "precheck")
        self.assertEqual(order[0][1], (6, 14, 2))
        self.assertEqual(
            order[0][2], pathlib.Path("/fake/maa") / "cache" / "resource" / "tasks.json"
        )
        self.assertEqual(order[1][0], "to_blackflow")
        mock_precheck.assert_called_once()
        # 每次 initialize_maa 后 append 一次 Custom 任务链
        maa.append_task.assert_called_once_with(
            "Custom", {"task_names": ["BlackFlowTemporary@Begin"]}
        )
        maa.start.assert_called_once_with()

    @patch.object(BaseSchedulerSolver, "__init__", lambda x: None)
    def test_bf_dispatch_precheck_failure_aborts_before_navigation(self):
        """验收 3：预检失败抛异常，走现有 except 路径，不进入 MAA 循环。"""
        maa = MagicMock()
        maa.get_version.return_value = "v6.13.9"
        solver = self._solver_with_maa(maa)

        with (
            patch.object(base_schedule, "send_message") as mock_send,
            patch.object(base_schedule, "save_exception"),
            patch.object(base_schedule, "csleep"),
            patch.object(base_schedule.config, "conf", make_conf()),
            patch.object(
                base_schedule,
                "check_blackflow_prereqs",
                side_effect=Exception(
                    "黑流树海刷钱需要 MAA ≥ v6.14.0，当前 6.13.9，请升级 MAA"
                ),
            ),
        ):
            solver.maa_plan_solver()

        solver.to_blackflow.assert_not_called()
        maa.append_task.assert_not_called()
        maa.start.assert_not_called()
        solver.device.exit.assert_called_once_with()
        self.assertIsNone(solver.MAA)
        mock_send.assert_has_calls(
            [
                call(
                    "黑流树海刷钱需要 MAA ≥ v6.14.0，当前 6.13.9，请升级 MAA",
                    "Maa调用出错！",
                    level="ERROR",
                )
            ]
        )
        # 预检失败是最后一次 send_message（错误通知）
        self.assertEqual(
            mock_send.call_args.args[0],
            "黑流树海刷钱需要 MAA ≥ v6.14.0，当前 6.13.9，请升级 MAA",
        )

    @patch.object(BaseSchedulerSolver, "__init__", lambda x: None)
    def test_rg_dispatch_unchanged_when_bf_not_set(self):
        """验收 6：conf.RG=True 仍走原 Roguelike 分支，BF 预检/导航不触发。"""
        maa = MagicMock()
        maa.get_version.return_value = "v6.14.2"
        maa.running.side_effect = [True, False]
        solver = self._solver_with_maa(maa)
        conf = make_conf(
            maa_long_task_type="rogue",
            maa_rg_theme="Mizuki",
            rogue=MagicMock(),
        )

        with (
            patch.object(base_schedule, "send_message"),
            patch.object(base_schedule, "save_exception"),
            patch.object(base_schedule, "csleep"),
            patch.object(base_schedule.config, "conf", conf),
            patch.object(
                base_schedule,
                "check_blackflow_prereqs",
                side_effect=AssertionError("BF 预检不应在 RG 分支触发"),
            ) as mock_precheck,
        ):
            solver.maa_plan_solver()

        mock_precheck.assert_not_called()
        solver.to_blackflow.assert_not_called()
        self.assertEqual(maa.append_task.call_args.args[0], "Roguelike")
        maa.start.assert_called_once_with()


class TestToBlackflowNavigation(unittest.TestCase):
    """导航 seam：to_blackflow 纯逻辑（场景序列驱动），验证点击序列与超时报错。"""

    def _make_solver(self) -> BaseSolver:
        solver = object.__new__(BaseSolver)
        solver.device = MagicMock()
        solver.recog = MagicMock()
        return solver

    def test_navigates_to_start_explore(self):
        """验收 4：INDEX→终端→长期探索→集成战略→黑流树海主题→开始探索界面。"""
        solver = self._make_solver()
        scenes = iter([Scene.INDEX, Scene.INDEX, Scene.TERMINAL_MAIN])
        integrated_strategy = ((100, 100), (200, 200))
        blackflow_theme = ((300, 300), (400, 400))
        start_explore = ((500, 500), (600, 600))
        finds = iter([integrated_strategy, blackflow_theme, start_explore])
        find_calls = []

        def fake_find(name, *args, **kwargs):
            find_calls.append(name)
            return next(finds)

        with (
            patch.object(BaseSolver, "scene", side_effect=lambda: next(scenes)),
            patch.object(BaseSolver, "find", side_effect=fake_find),
            patch.object(BaseSolver, "sleep"),
            patch.object(BaseSolver, "tap") as mock_tap,
            patch.object(BaseSolver, "tap_index_element") as mock_tap_index,
            patch.object(BaseSolver, "tap_terminal_button") as mock_tap_terminal,
        ):
            solver.to_blackflow()

        mock_tap_index.assert_called_once_with("terminal")
        mock_tap_terminal.assert_called_once_with("longterm")
        mock_tap.assert_has_calls(
            [
                call(integrated_strategy, interval=2),
                call(blackflow_theme, interval=2),
            ]
        )
        self.assertEqual(
            find_calls,
            ["bf/integrated_strategy", "bf/blackflow_theme", "bf/start_explore"],
        )

    def test_tolerates_missing_placeholder_templates(self):
        """验收 4：模板占位期 find 未命中 → 仅 warning，继续下一阶段直至开始探索界面。"""
        solver = self._make_solver()
        scenes = iter([Scene.INDEX, Scene.INDEX, Scene.TERMINAL_MAIN])
        start_explore = ((500, 500), (600, 600))
        finds = iter([None, None, start_explore])

        with (
            patch.object(BaseSolver, "scene", side_effect=lambda: next(scenes)),
            patch.object(BaseSolver, "find", side_effect=lambda *a, **k: next(finds)),
            patch.object(BaseSolver, "sleep"),
            patch.object(BaseSolver, "tap") as mock_tap,
            patch.object(BaseSolver, "tap_index_element") as mock_tap_index,
            patch.object(BaseSolver, "tap_terminal_button") as mock_tap_terminal,
        ):
            solver.to_blackflow()

        mock_tap_index.assert_called_once_with("terminal")
        mock_tap_terminal.assert_called_once_with("longterm")
        mock_tap.assert_not_called()

    def test_terminal_timeout_raises(self):
        """验收 4：未到达终端超过 30s → 抛异常。"""
        solver = self._make_solver()
        start_time = datetime(2026, 5, 2, 15, 19, 33)

        class FixedDateTime(datetime):
            now_value = start_time

            @classmethod
            def now(cls, tz=None):
                if tz is not None:
                    return cls.now_value.replace(tzinfo=tz)
                return cls.now_value

        def advance_sleep(*args, **kwargs):
            FixedDateTime.now_value = start_time + timedelta(seconds=31)

        with (
            patch.object(solver_module, "datetime", FixedDateTime),
            patch.object(BaseSolver, "scene", return_value=Scene.INDEX),
            patch.object(BaseSolver, "find", return_value=None),
            patch.object(BaseSolver, "sleep", side_effect=advance_sleep),
            patch.object(BaseSolver, "tap"),
            patch.object(BaseSolver, "tap_index_element"),
            patch.object(BaseSolver, "tap_terminal_button"),
        ):
            with self.assertRaisesRegex(Exception, "导航超时"):
                solver.to_blackflow()

    def test_start_explore_timeout_raises(self):
        """验收 4：长时间未进入“开始探索”界面（2 分钟）→ 抛异常。"""
        solver = self._make_solver()
        start_time = datetime(2026, 5, 2, 15, 19, 33)

        class FixedDateTime(datetime):
            now_value = start_time

            @classmethod
            def now(cls, tz=None):
                if tz is not None:
                    return cls.now_value.replace(tzinfo=tz)
                return cls.now_value

        def advance_sleep(*args, **kwargs):
            FixedDateTime.now_value = start_time + timedelta(minutes=3)

        with (
            patch.object(solver_module, "datetime", FixedDateTime),
            patch.object(BaseSolver, "scene", return_value=Scene.TERMINAL_MAIN),
            patch.object(BaseSolver, "find", return_value=None),
            patch.object(BaseSolver, "sleep", side_effect=advance_sleep),
            patch.object(BaseSolver, "tap"),
            patch.object(BaseSolver, "tap_index_element"),
            patch.object(BaseSolver, "tap_terminal_button"),
        ):
            with self.assertRaisesRegex(Exception, "导航超时"):
                solver.to_blackflow()


if __name__ == "__main__":
    unittest.main()
