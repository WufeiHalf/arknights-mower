import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import arknights_mower.solvers.base_schedule as base_schedule
from arknights_mower.solvers.base_schedule import BaseSchedulerSolver
from arknights_mower.utils.mastery_sync import MasterySync
from arknights_mower.utils.scheduler_task import SchedulerTask, TaskTypes


class TestMasterySkillUpgrade(unittest.TestCase):
    def setUp(self):
        self.solver = BaseSchedulerSolver.__new__(BaseSchedulerSolver)
        self.solver.tasks = []
        self.solver.op_data = MagicMock()
        self.solver.op_data.skill_upgrade_supports = [MagicMock(name="助手")]

    @patch("arknights_mower.utils.mastery_sync.get_skill_data")
    @patch("arknights_mower.utils.mastery_sync.get_route")
    @patch("arknights_mower.utils.mastery_sync.insert_plan")
    def test_mastery_sync_links_arrangement_and_upgrade_by_plan_key(
        self, insert_plan, get_route, get_skill_data
    ):
        get_skill_data.return_value = {
            "characters": {"char": {"name": "目标", "profession": "P"}}
        }
        get_route.return_value = {"supports": '[{"name": "助手", "level": 1}]'}
        scheduler = MagicMock()
        scheduler.tasks = []
        scheduler.op_data.skill_upgrade_supports = []
        with patch(
            "arknights_mower.utils.mastery_sync._supports_from_dicts"
        ) as supports:
            supports.return_value = [MagicMock(name="助手")]
            MasterySync(scheduler)._schedule_next(
                {"char_id": "char", "skill_index": 0, "level": 1}
            )
        self.assertEqual(len(scheduler.tasks), 2)
        self.assertEqual(scheduler.tasks[0].meta_data, "_mastery")
        self.assertEqual(scheduler.tasks[0].plan_key, "char_0")
        self.assertEqual(scheduler.tasks[1].plan_key, "char_0")
        insert_plan.assert_called_once()

    def test_mastery_task_is_not_protected_in_false_mode(self):
        upgrade = SchedulerTask(task_type=TaskTypes.SKILL_UPGRADE)
        self.solver.tasks = [upgrade]
        self.solver.task = SchedulerTask(
            task_plan={"train": ["助手", "目标"]}, meta_data="_mastery"
        )
        with patch.object(
            base_schedule.config.conf, "assistant_follows_schedule", False
        ):
            self.assertFalse(self.solver._should_protect_train_plan("train"))

    def test_mastery_arrange_room_enters_train_room(self):
        self.solver.tasks = [SchedulerTask(task_type=TaskTypes.SKILL_UPGRADE)]
        self.solver.task = SchedulerTask(
            task_plan={"train": ["助手", "目标"]}, meta_data="_mastery"
        )
        plan = {"train": ["助手", "目标"]}
        self.solver.enter_room = MagicMock()
        self.solver.turn_on_room_detail = MagicMock()
        self.solver.get_agent_from_room = MagicMock(
            return_value=[{"agent": "助手"}, {"agent": "目标"}]
        )
        self.solver.scene = MagicMock(return_value=base_schedule.Scene.INFRA_MAIN)
        self.solver.choose_train = MagicMock()
        self.solver.refresh_current_room = MagicMock()
        with patch.object(
            base_schedule.config.conf, "assistant_follows_schedule", False
        ):
            with patch.object(self.solver, "back"):
                self.solver.agent_arrange_room({}, "train", plan)
        self.solver.enter_room.assert_called_once_with("train")

    def test_normal_train_plan_is_protected_in_false_mode(self):
        self.solver.tasks = [SchedulerTask(task_type=TaskTypes.SKILL_UPGRADE)]
        self.solver.task = SchedulerTask(task_plan={"train": ["普通干员"]})
        with patch.object(
            base_schedule.config.conf, "assistant_follows_schedule", False
        ):
            self.assertTrue(self.solver._should_protect_train_plan("train"))
            self.assertFalse(self.solver._should_protect_train_plan("factory"))

    def test_true_mode_keeps_train_plan_compatible(self):
        self.solver.tasks = [SchedulerTask(task_type=TaskTypes.SKILL_UPGRADE)]
        self.solver.task = SchedulerTask(task_plan={"train": ["普通干员"]})
        with patch.object(
            base_schedule.config.conf, "assistant_follows_schedule", True
        ):
            self.assertFalse(self.solver._should_protect_train_plan("train"))

    @patch(
        "arknights_mower.utils.mastery_recommendation.get_skill_data",
        return_value={"characters": {"char": {"name": "目标"}}},
    )
    def test_target_must_be_in_second_training_slot(self, _get_skill_data):
        self.solver.get_agent_from_room = MagicMock(
            return_value=[{"agent": "助手"}, {"agent": "目标"}]
        )
        self.assertTrue(self.solver._mastery_target_in_training_room("char_0"))
        self.solver.get_agent_from_room.return_value = [
            {"agent": "目标"},
            {"agent": "助手"},
        ]
        self.assertFalse(self.solver._mastery_target_in_training_room("char_0"))
        self.solver.get_agent_from_room.return_value = []
        self.assertFalse(self.solver._mastery_target_in_training_room("char_0"))

    @patch(
        "arknights_mower.utils.mastery_recommendation.get_skill_data",
        return_value={"characters": {"char": {"name": "目标"}}},
    )
    def test_missing_target_rebuilds_one_delayed_mastery_task(self, _get_skill_data):
        self.solver.task = SchedulerTask(
            task_type=TaskTypes.SKILL_UPGRADE, meta_data="目标 技能1"
        )
        self.solver.task.plan_key = "char_0"
        duplicate = SchedulerTask(
            task_plan={"train": ["助手", "目标"]}, meta_data="_mastery"
        )
        duplicate.plan_key = "char_0"
        duplicate_upgrade = SchedulerTask(
            task_type=TaskTypes.SKILL_UPGRADE, meta_data="目标 技能1"
        )
        duplicate_upgrade.plan_key = "char_0"
        self.solver.tasks = [duplicate, duplicate_upgrade]
        self.solver.get_agent_from_room = MagicMock(return_value=[])
        now = datetime.now()
        with patch.object(base_schedule, "datetime") as mocked_datetime:
            mocked_datetime.now.return_value = now
            self.solver.skill_upgrade("目标 技能1")
        mastery_tasks = [
            task for task in self.solver.tasks if task.meta_data == "_mastery"
        ]
        self.assertEqual(len(mastery_tasks), 1)
        self.assertEqual(mastery_tasks[0].plan_key, "char_0")
        self.assertGreaterEqual(mastery_tasks[0].time, now + timedelta(seconds=5))
        upgrade_tasks = [
            task for task in self.solver.tasks if task.type == TaskTypes.SKILL_UPGRADE
        ]
        self.assertEqual(len(upgrade_tasks), 1)
        self.assertEqual(upgrade_tasks[0].plan_key, "char_0")
        self.assertGreaterEqual(upgrade_tasks[0].time, now + timedelta(seconds=6))

    @patch(
        "arknights_mower.utils.mastery_recommendation.get_skill_data",
        return_value={"characters": {"char": {"name": "目标"}}},
    )
    @patch(
        "arknights_mower.utils.mastery_recommendation.get_skill_data",
        return_value={"characters": {"char": {"name": "目标"}}},
    )
    def test_training_room_read_error_retries_without_failed_status(
        self, _get_skill_data
    ):
        self.solver.task = SchedulerTask(
            task_type=TaskTypes.SKILL_UPGRADE, meta_data="目标 技能1"
        )
        self.solver.task.plan_key = "char_0"
        self.solver.get_agent_from_room = MagicMock(side_effect=RuntimeError("read"))
        with patch("arknights_mower.utils.mastery_db.set_plan_status") as set_status:
            self.solver.skill_upgrade("目标 技能1")
        set_status.assert_not_called()
        self.assertTrue(any(task.meta_data == "_mastery" for task in self.solver.tasks))

    def test_true_mode_skips_mastery_target_guard(self):
        self.solver.task = SchedulerTask(
            task_type=TaskTypes.SKILL_UPGRADE, meta_data="目标 技能1"
        )
        self.solver.task.plan_key = "char_0"
        self.solver._mastery_target_in_training_room = MagicMock(
            side_effect=AssertionError("true mode must not guard")
        )
        with patch.object(
            base_schedule.config.conf, "assistant_follows_schedule", True
        ):
            with patch.object(self.solver, "train_scene", side_effect=RuntimeError):
                self.solver.skill_upgrade("目标 技能1")
        self.solver._mastery_target_in_training_room.assert_not_called()

    @patch(
        "arknights_mower.utils.mastery_recommendation.get_skill_data",
        return_value={"characters": {"char": {"name": "目标"}}},
    )
    def test_target_mismatch_does_not_tap_or_mark_failed(self, _get_skill_data):
        self.solver.task = SchedulerTask(
            task_type=TaskTypes.SKILL_UPGRADE, meta_data="目标 技能1"
        )
        self.solver.task.plan_key = "char_0"
        self.solver.get_agent_from_room = MagicMock(
            return_value=[{"agent": "助手"}, {"agent": "其他"}]
        )
        self.solver.tap = MagicMock()
        self.solver.ctap = MagicMock()
        with patch("arknights_mower.utils.mastery_db.set_plan_status") as set_status:
            self.solver.skill_upgrade("目标 技能1")
        self.solver.tap.assert_not_called()
        self.solver.ctap.assert_not_called()
        set_status.assert_not_called()


if __name__ == "__main__":
    unittest.main()
