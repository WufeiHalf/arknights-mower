import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import arknights_mower.solvers.base_schedule as base_schedule
from arknights_mower.solvers.base_schedule import BaseSchedulerSolver
from arknights_mower.utils import mastery_db
from arknights_mower.utils.mastery_sync import MasterySync
from arknights_mower.utils.recognize import Scene
from arknights_mower.utils.scheduler_task import SchedulerTask, TaskTypes


class TestMasterySkillUpgrade(unittest.TestCase):
    def setUp(self):
        self.solver = BaseSchedulerSolver.__new__(BaseSchedulerSolver)
        self.solver.tasks = []
        self.solver.op_data = MagicMock()
        self.solver.op_data.skill_upgrade_supports = []

    def _plan_context_patches(self, level=1, name="目标"):
        plan = {"char_id": "char", "skill_index": 0, "level": level}
        data = {"characters": {"char": {"name": name, "profession": "P"}}}
        return (
            patch(
                "arknights_mower.utils.mastery_db.get_in_progress_plan",
                return_value=plan,
            ),
            patch(
                "arknights_mower.utils.mastery_recommendation.get_skill_data",
                return_value=data,
            ),
        )

    def _mastery_task(self):
        task = SchedulerTask(task_type=TaskTypes.SKILL_UPGRADE, meta_data="目标 技能1")
        task.plan_key = "char_0"
        return task

    def test_mastery_sync_detects_snapshot_older_than_current_plan(self):
        training = {
            "lastUpdateTime": datetime(2026, 7, 14, 16, 12, 46).timestamp(),
        }
        plan = {"created_at": "2026-07-14 16:15:46"}

        self.assertTrue(MasterySync._training_snapshot_is_stale(training, plan))

        training["lastUpdateTime"] = datetime(2026, 7, 14, 16, 16).timestamp()
        self.assertFalse(MasterySync._training_snapshot_is_stale(training, plan))

    def test_mastery_sync_schedules_collection_for_expired_completed_training(self):
        scheduler = MagicMock()
        scheduler.tasks = []
        training = {
            "trainee": {"charId": "char", "targetSkill": 0},
            "trainer": {"charId": "support"},
            "remainSecs": 0,
            "slotState": 2,
        }
        plan = {
            "char_id": "char",
            "skill_index": 0,
            "level": 1,
            "expires_at": "2026-07-13 22:12:37",
        }
        sync = MasterySync(scheduler)
        with (
            patch.object(sync, "_refresh_skland_data"),
            patch(
                "arknights_mower.utils.mastery_sync.has_train_group_plan",
                return_value=False,
            ),
            patch(
                "arknights_mower.utils.mastery_sync.get_in_progress_plan",
                return_value=plan,
            ),
            patch(
                "arknights_mower.solvers.player_info.player_info_cache",
                {"latest": {"building_training": training}},
            ),
        ):
            sync.sync_and_schedule()

        self.assertEqual(len(scheduler.tasks), 1)
        self.assertEqual(scheduler.tasks[0].type, TaskTypes.REFRESH_TIME)
        self.assertEqual(scheduler.tasks[0].meta_data, "train")

    def test_mastery_sync_does_not_treat_slot_state_two_as_completion(self):
        scheduler = MagicMock()
        scheduler.tasks = []
        training = {
            "trainee": {"charId": "char", "targetSkill": 0},
            "trainer": {"charId": "support"},
            "remainSecs": 3600,
            "slotState": 2,
        }
        plan = {
            "char_id": "char",
            "skill_index": 0,
            "level": 1,
            "expires_at": "2026-07-13 22:12:37",
        }
        sync = MasterySync(scheduler)
        with (
            patch.object(sync, "_refresh_skland_data"),
            patch(
                "arknights_mower.utils.mastery_sync.has_train_group_plan",
                return_value=False,
            ),
            patch(
                "arknights_mower.utils.mastery_sync.get_in_progress_plan",
                return_value=plan,
            ),
            patch("arknights_mower.utils.mastery_sync.set_plan_status") as set_status,
            patch(
                "arknights_mower.solvers.player_info.player_info_cache",
                {"latest": {"building_training": training}},
            ),
        ):
            sync.sync_and_schedule()

        set_status.assert_called_once()
        self.assertEqual(len(scheduler.tasks), 1)
        self.assertEqual(scheduler.tasks[0].type, TaskTypes.REFRESH_TIME)

    def test_mastery_sync_links_arrangement_and_upgrade_by_plan_key(self):
        scheduler = MagicMock()
        scheduler.tasks = []
        scheduler.op_data.skill_upgrade_supports = []
        support = MagicMock()
        support.name = "助手"
        support.level = 1
        with (
            patch(
                "arknights_mower.utils.mastery_sync.get_skill_data",
                return_value={
                    "characters": {"char": {"name": "目标", "profession": "P"}}
                },
            ),
            patch(
                "arknights_mower.utils.mastery_sync.get_route",
                return_value={"supports": "[]"},
            ),
            patch("arknights_mower.utils.mastery_sync.insert_plan") as insert_plan,
            patch(
                "arknights_mower.utils.mastery_recommendation._supports_from_dicts",
                return_value=[support],
            ),
        ):
            MasterySync(scheduler)._schedule_next(
                {"char_id": "char", "skill_index": 0, "level": 1}
            )
        self.assertEqual(len(scheduler.tasks), 2)
        self.assertEqual(scheduler.tasks[0].meta_data, "_mastery")
        self.assertEqual(scheduler.tasks[0].plan_key, "char_0")
        self.assertEqual(scheduler.tasks[1].plan_key, "char_0")
        insert_plan.assert_called_once()

    def test_schedule_next_selects_support_for_target_level(self):
        scheduler = MagicMock()
        scheduler.tasks = []
        support1 = MagicMock(level=1, swap=True, swap_name="逻各斯")
        support1.name = "罗宾"
        support2 = MagicMock(level=2, swap=True, swap_name="逻各斯")
        support2.name = "罗宾"
        support3 = MagicMock(level=3, swap=False, swap_name="逻各斯")
        support3.name = "望"
        with (
            patch(
                "arknights_mower.utils.mastery_sync.get_skill_data",
                return_value={
                    "characters": {"char": {"name": "目标", "profession": "P"}}
                },
            ),
            patch(
                "arknights_mower.utils.mastery_sync.get_route",
                return_value={"supports": "[]"},
            ),
            patch("arknights_mower.utils.mastery_sync.insert_plan"),
            patch(
                "arknights_mower.utils.mastery_recommendation._supports_from_dicts",
                return_value=[support1, support2, support3],
            ),
        ):
            MasterySync(scheduler)._schedule_next(
                {"char_id": "char", "skill_index": 0, "level": 3}
            )

        self.assertEqual(scheduler.tasks[0].plan["train"], ["望", "目标"])

    def test_schedule_next_keeps_logos_for_next_mastery(self):
        scheduler = MagicMock()
        scheduler.tasks = []
        support1 = MagicMock(level=1, swap=True, swap_name="逻各斯")
        support1.name = "罗宾"
        support2 = MagicMock(level=2, swap=True, swap_name="逻各斯")
        support2.name = "罗宾"
        support3 = MagicMock(level=3, swap=False, swap_name="逻各斯")
        support3.name = "望"
        training = {
            "trainee": {"charId": "char", "targetSkill": 0},
            "trainer": {"charId": "logos"},
            "remainSecs": 0,
        }
        with (
            patch(
                "arknights_mower.utils.mastery_sync.get_skill_data",
                return_value={
                    "characters": {
                        "char": {"name": "目标", "profession": "P"},
                        "logos": {"name": "逻各斯"},
                    }
                },
            ),
            patch(
                "arknights_mower.utils.mastery_sync.get_route",
                return_value={"supports": "[]"},
            ),
            patch("arknights_mower.utils.mastery_sync.insert_plan"),
            patch(
                "arknights_mower.utils.mastery_recommendation._supports_from_dicts",
                return_value=[support1, support2, support3],
            ),
            patch(
                "arknights_mower.solvers.player_info.player_info_cache",
                {"latest": {"building_training": training}},
            ),
        ):
            MasterySync(scheduler)._schedule_next(
                {"char_id": "char", "skill_index": 0, "level": 3}
            )

        self.assertEqual(scheduler.tasks[0].plan["train"], ["Current", "目标"])

    def test_mastery_completion_only_creates_pending_next_level(self):
        training = {
            "trainee": {"charId": "char", "targetSkill": 0},
        }
        self.solver.tasks = []
        with (
            patch(
                "arknights_mower.solvers.player_info.player_info_cache",
                {"latest": {"building_training": training}},
            ),
            patch(
                "arknights_mower.utils.mastery_db.get_in_progress_plan",
                return_value={"char_id": "char", "skill_index": 0, "level": 2},
            ),
            patch("arknights_mower.utils.mastery_db.insert_plan") as insert_plan,
            patch(
                "arknights_mower.utils.mastery_recommendation.get_skill_data",
                return_value={"characters": {"char": {"name": "目标"}}},
            ),
        ):
            self.solver._handle_training_complete()

        self.assertEqual(insert_plan.call_count, 2)
        self.assertEqual(insert_plan.call_args_list[0].args[2], "completed")
        self.assertEqual(insert_plan.call_args_list[1].args[2], "pending")
        self.assertEqual(self.solver.tasks, [])

    def test_half_duration_mastery_uses_plan_level(self):
        task = self._mastery_task()
        self.solver.task = task
        support = MagicMock(level=3)
        support.name = "望"
        self.solver.op_data.skill_upgrade_supports = [support]
        finish = datetime.now() + timedelta(hours=12)
        self.solver.train_scene = MagicMock(
            side_effect=[
                Scene.TRAIN_MAIN,
                Scene.TRAIN_MAIN,
                Scene.TRAIN_SKILL_SELECT,
                Scene.TRAIN_SKILL_UPGRADE,
                Scene.TRAIN_SKILL_UPGRADE,
                Scene.TRAIN_MAIN,
            ]
        )
        self.solver.find = MagicMock(side_effect=[None, True])
        self.solver.double_read_time = MagicMock(side_effect=[finish, finish, finish])
        self.solver.tap = MagicMock()
        self.solver.ctap = MagicMock()
        self.solver.sleep = MagicMock()
        self.solver.back = MagicMock()
        self.solver.recog = MagicMock(w=1000, h=1000)
        with (
            patch.object(
                base_schedule.config.conf, "assistant_follows_schedule", False
            ),
            patch.object(
                self.solver,
                "_mastery_context",
                return_value=({"level": 3}, {}, "目标", 0),
            ),
            patch.object(
                self.solver, "_mastery_target_in_training_room", return_value=True
            ),
            patch("arknights_mower.utils.mastery_db.set_plan_status") as set_status,
        ):
            self.solver.skill_upgrade(task.meta_data)

        self.assertTrue(
            any(
                call.args[2] == "in_progress" and call.kwargs["level"] == 3
                for call in set_status.call_args_list
            )
        )
        mastery_tasks = [
            queued for queued in self.solver.tasks if queued.meta_data == "_mastery"
        ]
        self.assertEqual(len(mastery_tasks), 1)
        self.assertEqual(mastery_tasks[0].plan["train"], ["望", "Current"])

    def test_material_failure_keeps_carryover_assistant(self):
        task = self._mastery_task()
        self.solver.task = task
        support = MagicMock(level=3)
        support.name = "望"
        self.solver.op_data.skill_upgrade_supports = [support]
        finish = datetime.now() + timedelta(hours=12)
        self.solver.train_scene = MagicMock(
            side_effect=[
                Scene.TRAIN_MAIN,
                Scene.TRAIN_MAIN,
                Scene.TRAIN_SKILL_SELECT,
                Scene.TRAIN_SKILL_UPGRADE,
                Scene.TRAIN_SKILL_UPGRADE_ERROR,
            ]
        )
        self.solver.find = MagicMock(side_effect=[None, True])
        self.solver.double_read_time = MagicMock(return_value=finish)
        self.solver.tap = MagicMock()
        self.solver.ctap = MagicMock()
        self.solver.sleep = MagicMock()
        self.solver.back = MagicMock()
        self.solver.recog = MagicMock(w=1000, h=1000)
        with (
            patch.object(
                base_schedule.config.conf, "assistant_follows_schedule", False
            ),
            patch.object(
                self.solver,
                "_mastery_context",
                return_value=({"level": 3}, {}, "目标", 0),
            ),
            patch.object(
                self.solver, "_mastery_target_in_training_room", return_value=True
            ),
            patch("arknights_mower.utils.mastery_db.set_plan_status") as set_status,
            patch("arknights_mower.solvers.base_schedule.send_message"),
        ):
            self.solver.skill_upgrade(task.meta_data)

        self.assertTrue(
            any(
                call.args[2] == "failed"
                and call.args[3] == "材料不足 level3"
                and call.kwargs["level"] == 3
                for call in set_status.call_args_list
            )
        )
        self.assertFalse(
            any(queued.meta_data == "_mastery" for queued in self.solver.tasks)
        )

    def test_retry_restores_level_from_legacy_failure_reason(self):
        with (
            patch.object(
                mastery_db,
                "get_current_plan",
                return_value={
                    "status": "failed",
                    "level": 1,
                    "failed_reason": "材料不足 level3",
                },
            ),
            patch.object(mastery_db, "insert_plan", return_value=123) as insert_plan,
        ):
            plan_id = mastery_db.retry_plan("char", 0)

        self.assertEqual(plan_id, 123)
        self.assertEqual(insert_plan.call_args.kwargs["level"], 3)

    def test_mastery_task_is_not_protected_in_false_mode(self):
        self.solver.tasks = [SchedulerTask(task_type=TaskTypes.SKILL_UPGRADE)]
        self.solver.task = SchedulerTask(
            task_plan={"train": ["助手", "目标"]}, meta_data="_mastery"
        )
        with patch.object(
            base_schedule.config.conf, "assistant_follows_schedule", False
        ):
            self.assertFalse(self.solver._should_protect_train_plan("train"))

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
        self.solver.scene = MagicMock(return_value=Scene.INFRA_MAIN)
        self.solver.choose_train = MagicMock()
        self.solver.refresh_current_room = MagicMock()
        with patch.object(
            base_schedule.config.conf, "assistant_follows_schedule", False
        ):
            with patch.object(self.solver, "back"):
                self.solver.agent_arrange_room({}, "train", plan)
        self.solver.enter_room.assert_called_once_with("train")

    def test_infra_main_consumes_real_retry_path_without_dropping_new_tasks(self):
        original = self._mastery_task()
        unrelated = SchedulerTask(
            task_type=TaskTypes.NOT_SPECIFIC, meta_data="unrelated"
        )
        self.solver.tasks = [original, unrelated]
        self.solver.task = original
        self.solver.find = MagicMock(return_value=True)
        support = MagicMock(level=1)
        support.name = "正确助手"
        self.solver.op_data.skill_upgrade_supports = [support]
        self.solver.get_agent_from_room = MagicMock(return_value=[])
        with (
            patch.object(
                base_schedule.config.conf, "assistant_follows_schedule", False
            ),
            patch(
                "arknights_mower.utils.mastery_db.get_in_progress_plan",
                return_value={"char_id": "char", "skill_index": 0, "level": 1},
            ),
            patch(
                "arknights_mower.utils.mastery_recommendation.get_skill_data",
                return_value={
                    "characters": {"char": {"name": "目标", "profession": "P"}}
                },
            ),
        ):
            self.solver.infra_main()
        retry_mastery = [
            task for task in self.solver.tasks if task.meta_data == "_mastery"
        ][0]
        retry_upgrade = [
            task for task in self.solver.tasks if task.type == TaskTypes.SKILL_UPGRADE
        ][0]
        self.assertNotIn(original, self.solver.tasks)
        self.assertIn(unrelated, self.solver.tasks)
        self.assertEqual(retry_mastery.plan_key, "char_0")
        self.assertEqual(retry_upgrade.plan_key, "char_0")
        self.solver.task = retry_mastery
        self.solver.agent_arrange = MagicMock()
        self.solver.infra_main()
        self.assertNotIn(retry_mastery, self.solver.tasks)
        self.assertIn(retry_upgrade, self.solver.tasks)
        self.assertIn(unrelated, self.solver.tasks)

    def test_actual_mismatched_target_is_retried(self):
        self.solver.get_agent_from_room = MagicMock(
            return_value=[{"agent": "助手"}, {"agent": "其他"}]
        )
        with self._plan_context_patches()[0], self._plan_context_patches()[1]:
            self.assertFalse(self.solver._mastery_target_in_training_room("char_0"))

    def test_target_in_second_slot_does_not_repeat_arrangement(self):
        self.solver.get_agent_from_room = MagicMock(
            return_value=[{"agent": "助手"}, {"agent": "目标"}]
        )
        with self._plan_context_patches()[0], self._plan_context_patches()[1]:
            self.assertTrue(self.solver._mastery_target_in_training_room("char_0"))
        self.solver.get_agent_from_room.assert_called_once_with("train")

    def test_empty_mismatched_none_and_invalid_slots_are_safe(self):
        for value in (
            [],
            [{"agent": "助手"}],
            None,
            {"agent": "目标"},
            [{"bad": "目标"}, None],
        ):
            with self.subTest(value=value):
                self.solver.get_agent_from_room = MagicMock(return_value=value)
                with self._plan_context_patches()[0], self._plan_context_patches()[1]:
                    self.assertFalse(
                        self.solver._mastery_target_in_training_room("char_0")
                    )

    def test_training_read_error_does_not_write_failed(self):
        task = self._mastery_task()
        self.solver.task = task
        self.solver.op_data.skill_upgrade_supports = [MagicMock(level=1, name="助手")]
        self.solver.get_agent_from_room = MagicMock(side_effect=RuntimeError("read"))
        with (
            self._plan_context_patches()[0],
            self._plan_context_patches()[1],
            patch("arknights_mower.utils.mastery_db.set_plan_status") as set_status,
        ):
            self.solver.skill_upgrade(task.meta_data)
        set_status.assert_not_called()
        self.assertTrue(any(item.meta_data == "_mastery" for item in self.solver.tasks))

    def test_malformed_plan_key_is_safe_without_tap_or_failed(self):
        for plan_key in ("bad", "char_x", "missing_0"):
            with self.subTest(plan_key=plan_key):
                task = SchedulerTask(
                    task_type=TaskTypes.SKILL_UPGRADE, meta_data="目标 技能1"
                )
                task.plan_key = plan_key
                self.solver.task = task
                self.solver.tap = MagicMock()
                with patch(
                    "arknights_mower.utils.mastery_db.set_plan_status"
                ) as set_status:
                    self.solver.skill_upgrade(task.meta_data)
                self.solver.tap.assert_not_called()
                set_status.assert_not_called()

    def test_malformed_db_plan_is_safe(self):
        task = self._mastery_task()
        self.solver.task = task
        self.solver.tap = MagicMock()
        with (
            patch(
                "arknights_mower.utils.mastery_db.get_in_progress_plan",
                return_value={"char_id": "char"},
            ),
            patch(
                "arknights_mower.utils.mastery_recommendation.get_skill_data",
                return_value={"characters": {"char": {"name": "目标"}}},
            ),
            patch("arknights_mower.utils.mastery_db.set_plan_status") as set_status,
        ):
            self.solver.skill_upgrade(task.meta_data)
        self.solver.tap.assert_not_called()
        set_status.assert_not_called()

    def test_missing_support_requeues_upgrade_without_tap_or_failed(self):
        task = self._mastery_task()
        self.solver.task = task
        self.solver.tap = MagicMock()
        now = datetime.now()
        with (
            patch.object(base_schedule, "datetime") as mocked_datetime,
            self._plan_context_patches()[0],
            self._plan_context_patches()[1],
            patch("arknights_mower.utils.mastery_db.set_plan_status") as set_status,
        ):
            mocked_datetime.now.return_value = now
            self.solver.skill_upgrade(task.meta_data)
        self.solver.tap.assert_not_called()
        set_status.assert_not_called()
        retries = [
            item for item in self.solver.tasks if item.type == TaskTypes.SKILL_UPGRADE
        ]
        self.assertEqual(len(retries), 1)
        self.assertGreaterEqual(retries[0].time, now + timedelta(seconds=5))

    def test_retry_uses_current_level_support_and_deduplicates_by_plan_key(self):
        task = self._mastery_task()
        self.solver.task = task
        support1 = MagicMock(level=1)
        support1.name = "低级助手"
        support2 = MagicMock(level=2)
        support2.name = "正确助手"
        self.solver.op_data.skill_upgrade_supports = [support1, support2]
        duplicate = SchedulerTask(
            task_plan={"train": ["旧", "目标"]}, meta_data="_mastery"
        )
        duplicate.plan_key = "char_0"
        self.solver.tasks = [
            duplicate,
            SchedulerTask(task_type=TaskTypes.SKILL_UPGRADE, meta_data="other"),
        ]
        now = datetime.now()
        with (
            patch.object(base_schedule, "datetime") as mocked_datetime,
            patch(
                "arknights_mower.utils.mastery_db.get_in_progress_plan",
                return_value={"char_id": "char", "skill_index": 0, "level": 2},
            ),
            patch(
                "arknights_mower.utils.mastery_recommendation.get_skill_data",
                return_value={
                    "characters": {"char": {"name": "目标", "profession": "P"}}
                },
            ),
        ):
            mocked_datetime.now.return_value = now
            self.solver.get_agent_from_room = MagicMock(return_value=[])
            self.solver.skill_upgrade(task.meta_data)
        mastery = [item for item in self.solver.tasks if item.meta_data == "_mastery"]
        self.assertEqual(len(mastery), 1)
        self.assertEqual(mastery[0].plan["train"][0], "正确助手")
        self.assertGreaterEqual(mastery[0].time, now + timedelta(seconds=5))

    def test_level3_no_mid_swap_even_if_stale_snapshot_shows_previous_assistant(self):
        """L3 swap=false must win over a stale trainer name from lower levels."""
        finish = datetime.now() + timedelta(hours=12)
        support1 = MagicMock(level=1, swap=True, swap_name="逻各斯")
        support1.name = "罗宾"
        support2 = MagicMock(level=2, swap=True, swap_name="逻各斯")
        support2.name = "罗宾"
        support3 = MagicMock(level=3, swap=False, swap_name="逻各斯")
        support3.name = "望"
        self.solver.op_data.skill_upgrade_supports = [support1, support2, support3]
        self.solver.op_data.calculate_switch_time.return_value = 4
        self.solver.train_scene = MagicMock(return_value=Scene.TRAIN_MAIN)
        self.solver.double_read_time = MagicMock(return_value=finish)
        self.solver.back = MagicMock()
        self.solver.sleep = MagicMock()

        with (
            patch("arknights_mower.solvers.base_schedule.PlayerInfoClient"),
            patch(
                "arknights_mower.solvers.player_info.player_info_cache",
                {
                    "latest": {
                        "building_training": {
                            "trainee": {"charId": "char", "targetSkill": 0},
                            # Stale: previous level's assistant still in snapshot
                            "trainer": {"charId": "robin"},
                        }
                    }
                },
            ),
            patch(
                "arknights_mower.utils.mastery_db.get_in_progress_plan",
                return_value={
                    "char_id": "char",
                    "skill_index": 0,
                    "level": 3,
                },
            ),
            patch(
                "arknights_mower.utils.mastery_recommendation.get_skill_data",
                return_value={"characters": {"robin": {"name": "罗宾"}}},
            ),
            patch("arknights_mower.utils.mastery_db.set_plan_status"),
        ):
            self.solver.refresh_skill_time()

        mid_swaps = [
            task
            for task in self.solver.tasks
            if task.meta_data == "_mastery"
            and task.plan == {"train": ["逻各斯", "Current"]}
        ]
        self.assertEqual(mid_swaps, [])

    def _specialty_route_supports(self):
        support1 = MagicMock(level=1, swap=True, swap_name="逻各斯")
        support1.name = "罗宾"
        support2 = MagicMock(level=2, swap=True, swap_name="逻各斯")
        support2.name = "罗宾"
        support3 = MagicMock(level=3, swap=False, swap_name="逻各斯")
        support3.name = "望"
        return [support1, support2, support3]

    def _mid_swap_to_logos(self):
        return [
            task
            for task in self.solver.tasks
            if task.meta_data == "_mastery"
            and task.plan == {"train": ["逻各斯", "Current"]}
        ]

    def _run_refresh_for_level(self, level, trainer_char_id, trainer_name, hours=8):
        finish = datetime.now() + timedelta(hours=hours)
        self.solver.tasks = []
        self.solver.op_data.skill_upgrade_supports = self._specialty_route_supports()
        self.solver.op_data.calculate_switch_time.return_value = 3
        self.solver.train_scene = MagicMock(return_value=Scene.TRAIN_MAIN)
        self.solver.double_read_time = MagicMock(return_value=finish)
        self.solver.back = MagicMock()
        self.solver.sleep = MagicMock()
        with (
            patch("arknights_mower.solvers.base_schedule.PlayerInfoClient"),
            patch(
                "arknights_mower.solvers.player_info.player_info_cache",
                {
                    "latest": {
                        "building_training": {
                            "trainee": {"charId": "char", "targetSkill": 0},
                            "trainer": {"charId": trainer_char_id},
                        }
                    }
                },
            ),
            patch(
                "arknights_mower.utils.mastery_db.get_in_progress_plan",
                return_value={
                    "char_id": "char",
                    "skill_index": 0,
                    "level": level,
                },
            ),
            patch(
                "arknights_mower.utils.mastery_recommendation.get_skill_data",
                return_value={"characters": {trainer_char_id: {"name": trainer_name}}},
            ),
            patch("arknights_mower.utils.mastery_db.set_plan_status"),
        ):
            self.solver.refresh_skill_time()

    def test_level1_mid_swap_still_uses_plan_level_route(self):
        self._run_refresh_for_level(1, "robin", "罗宾")
        mid_swaps = self._mid_swap_to_logos()
        self.assertEqual(len(mid_swaps), 1)
        self.assertEqual(mid_swaps[0].plan_key, "char_0")

    def test_specialty_full_mastery_assistant_flow(self):
        """罗宾→逻各斯 / 逻各斯→罗宾→逻各斯 / 逻各斯→望(不中途换)."""
        supports = self._specialty_route_supports()
        skill_data = {
            "characters": {
                "char": {"name": "麒麟R夜刀", "profession": "SPECIAL"},
                "logos": {"name": "逻各斯"},
            }
        }

        def schedule(level, training=None):
            scheduler = MagicMock()
            scheduler.tasks = []
            with (
                patch(
                    "arknights_mower.utils.mastery_sync.get_skill_data",
                    return_value=skill_data,
                ),
                patch(
                    "arknights_mower.utils.mastery_sync.get_route",
                    return_value={"supports": "[]"},
                ),
                patch("arknights_mower.utils.mastery_sync.insert_plan"),
                patch(
                    "arknights_mower.utils.mastery_recommendation._supports_from_dicts",
                    return_value=supports,
                ),
                patch(
                    "arknights_mower.solvers.player_info.player_info_cache",
                    {
                        "latest": {
                            "building_training": training or {},
                        }
                    },
                ),
            ):
                MasterySync(scheduler)._schedule_next(
                    {"char_id": "char", "skill_index": 0, "level": level}
                )
            return scheduler.tasks

        # L1: no prior swap assistant → arrange 罗宾
        l1_tasks = schedule(1)
        self.assertEqual(l1_tasks[0].plan["train"], ["罗宾", "麒麟R夜刀"])

        # L1 mid-training with 罗宾 → schedule 逻各斯
        self._run_refresh_for_level(1, "robin", "罗宾")
        self.assertEqual(len(self._mid_swap_to_logos()), 1)

        # L2: keep 逻各斯 for start, then main assistant is 罗宾
        l2_training = {
            "trainee": {"charId": "char", "targetSkill": 0},
            "trainer": {"charId": "logos"},
            "remainSecs": 0,
        }
        l2_tasks = schedule(2, l2_training)
        self.assertEqual(l2_tasks[0].plan["train"], ["Current", "麒麟R夜刀"])

        # L2 mid-training after 罗宾 is in place → schedule 逻各斯 again
        self._run_refresh_for_level(2, "robin", "罗宾")
        self.assertEqual(len(self._mid_swap_to_logos()), 1)

        # L3: keep 逻各斯 for start, main assistant becomes 望
        l3_tasks = schedule(3, l2_training)
        self.assertEqual(l3_tasks[0].plan["train"], ["Current", "麒麟R夜刀"])

        # After L3 starts, even a stale 罗宾 snapshot must not mid-swap
        self._run_refresh_for_level(3, "robin", "罗宾", hours=12)
        self.assertEqual(self._mid_swap_to_logos(), [])

        # L3 with 望 in room also must not mid-swap
        self._run_refresh_for_level(3, "wang", "望", hours=12)
        self.assertEqual(self._mid_swap_to_logos(), [])

    def test_refresh_skill_time_refreshes_snapshot_before_swap_calculation(self):
        finish = datetime.now() + timedelta(hours=5)
        support = MagicMock()
        support.name = "罗宾"
        support.level = 1
        support.swap = True
        support.swap_name = "逻各斯"
        self.solver.op_data.skill_upgrade_supports = [support]
        self.solver.op_data.calculate_switch_time.return_value = 2
        self.solver.train_scene = MagicMock(return_value=Scene.TRAIN_MAIN)
        self.solver.double_read_time = MagicMock(return_value=finish)
        self.solver.back = MagicMock()
        self.solver.sleep = MagicMock()
        with (
            patch("arknights_mower.solvers.base_schedule.PlayerInfoClient") as client,
            patch(
                "arknights_mower.solvers.player_info.player_info_cache",
                {
                    "latest": {
                        "building_training": {
                            "trainee": {"charId": "char", "targetSkill": 0},
                            "trainer": {"charId": "robin"},
                        }
                    }
                },
            ),
            patch(
                "arknights_mower.utils.mastery_db.get_in_progress_plan",
                return_value={
                    "char_id": "char",
                    "skill_index": 0,
                    "level": 1,
                },
            ),
            patch(
                "arknights_mower.utils.mastery_recommendation.get_skill_data",
                return_value={"characters": {"robin": {"name": "罗宾"}}},
            ),
            patch("arknights_mower.utils.mastery_db.set_plan_status"),
        ):
            self.solver.refresh_skill_time()
            self.solver.refresh_skill_time()

        self.assertEqual(
            client.return_value.get_first_available_snapshot.call_count,
            2,
        )
        mastery_tasks = [
            task for task in self.solver.tasks if task.meta_data == "_mastery"
        ]
        refresh_tasks = [
            task
            for task in self.solver.tasks
            if task.type == TaskTypes.REFRESH_TIME and task.meta_data == "train"
        ]
        self.assertEqual(len(mastery_tasks), 1)
        self.assertEqual(len(refresh_tasks), 1)
        self.assertEqual(mastery_tasks[0].plan["train"], ["逻各斯", "Current"])

    def test_update_expires_at_uses_local_database_time(self):
        completion_time = datetime(2026, 7, 14, 5, 17, 8)
        with (
            patch(
                "arknights_mower.utils.mastery_db.get_in_progress_plan",
                return_value={"char_id": "char", "skill_index": 0, "level": 1},
            ),
            patch("arknights_mower.utils.mastery_db.set_plan_status") as set_status,
        ):
            self.solver._update_expires_at(completion_time)

        self.assertEqual(
            set_status.call_args.kwargs["expires_at"],
            "2026-07-14 05:17:08",
        )

    def test_success_path_sets_expires_at_after_skill_selection(self):
        task = self._mastery_task()
        self.solver.task = task
        support = MagicMock(level=1)
        support.name = "助手"
        self.solver.op_data.skill_upgrade_supports = [support]
        finish = datetime.now() + timedelta(hours=10)
        self.solver.train_scene = MagicMock(
            side_effect=[
                Scene.TRAIN_MAIN,
                Scene.TRAIN_MAIN,
                Scene.TRAIN_SKILL_SELECT,
                Scene.TRAIN_SKILL_UPGRADE,
                Scene.TRAIN_SKILL_UPGRADE,
                Scene.TRAIN_MAIN,
            ]
        )
        self.solver.find = MagicMock(side_effect=[None, True])
        self.solver.double_read_time = MagicMock(side_effect=[finish, finish, finish])
        self.solver.tap = MagicMock()
        self.solver.ctap = MagicMock()
        self.solver.sleep = MagicMock()
        self.solver.back = MagicMock()
        self.solver.recog = MagicMock(w=1000, h=1000)
        with (
            patch.object(
                base_schedule.config.conf, "assistant_follows_schedule", False
            ),
            patch.object(
                self.solver,
                "_mastery_context",
                return_value=({"level": 1}, {}, "目标", 0),
            ),
            patch.object(
                self.solver, "_mastery_target_in_training_room", return_value=True
            ),
            patch("arknights_mower.utils.mastery_db.set_plan_status") as set_status,
        ):
            self.solver.skill_upgrade(task.meta_data)
        self.assertTrue(
            any(
                call.args[2] == "in_progress" and call.kwargs["expires_at"]
                for call in set_status.call_args_list
            )
        )
        self.solver.tap.assert_called()

    def test_true_mode_skips_false_mode_target_guard(self):
        task = self._mastery_task()
        self.solver.task = task
        self.solver._mastery_target_in_training_room = MagicMock(
            side_effect=AssertionError("guard")
        )
        with patch.object(
            base_schedule.config.conf, "assistant_follows_schedule", True
        ):
            with patch.object(
                self.solver, "train_scene", side_effect=RuntimeError("stop")
            ):
                self.solver.skill_upgrade(task.meta_data)
        self.solver._mastery_target_in_training_room.assert_not_called()


if __name__ == "__main__":
    unittest.main()
