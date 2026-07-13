# 修复自动专精任务无法推进 Tasks

## Behavior Matrix

| Row | Applies? | Verification |
| --- | --- | --- |
| Primary path | yes | `test_success_path_sets_expires_at_after_skill_selection`; targeted mastery 16/16 |
| Alternate input or entrypoint | yes | `test_mastery_sync_links_arrangement_and_upgrade_by_plan_key`; `test_infra_main_consumes_real_retry_path_without_dropping_new_tasks` |
| Empty or missing input | yes | `test_empty_mismatched_none_and_invalid_slots_are_safe`; `test_missing_support_requeues_upgrade_without_tap_or_failed` |
| Invalid or malformed input | yes | `test_malformed_plan_key_is_safe_without_tap_or_failed`; `test_malformed_db_plan_is_safe` |
| Unavailable or not-ready dependency | yes | `test_training_read_error_does_not_write_failed`; `test_actual_mismatched_target_is_retried` |
| Duplicate or idempotent case | yes | `test_retry_uses_current_level_support_and_deduplicates_by_plan_key`; `test_target_in_second_slot_does_not_repeat_arrangement` |
| Boundary or limit case | yes | `test_mastery_task_is_not_protected_in_false_mode`; `test_normal_train_plan_is_protected_in_false_mode`; `test_true_mode_keeps_train_plan_compatible` |
| Existing behavior compatibility | yes | `test_true_mode_skips_false_mode_target_guard`; `base_scheduler_tests` 7/7 |
| Real entrypoint or integration path | yes | `test_infra_main_consumes_real_retry_path_without_dropping_new_tasks`; related suite 37/37; E3/E4 gated |

## Slice 1: 保护专精临时换班任务

- Status: completed
- Goal: `meta_data="_mastery"` 的训练室换班任务在 false 模式正常执行。
- Scope: 普通训练室排班保护条件与任务身份判定。
- Matrix rows: Primary path, Alternate input or entrypoint, Duplicate or idempotent case, Boundary or limit case, Existing behavior compatibility。
- Public behavior: 队列同时存在 `_mastery` 和 `SKILL_UPGRADE` 时，前者仍进入 `agent_arrange_room()`/`choose_train()`；普通训练室排班仍受保护；true 模式不变。
- Tests: 任务队列与 `agent_arrange_room()` 行为测试，验证 `_mastery` 不被删除、普通任务仍受保护、true/false 分支不混淆。
- Implementation notes: 复用已有 `SchedulerTask` 任务身份，不新增平行状态机。
- Verification: `mastery_skill_upgrade_tests` 16/16、`scheduler_task_tests` 14/14、`base_scheduler_tests` 7/7 通过；Ruff、format、compileall、diff-check 通过。真实 `infra_main` 两轮消费路径由 `test_infra_main_consumes_real_retry_path_without_dropping_new_tasks` 覆盖。
- Review: required
- Review verdict: PASS after Round 1 and final review fixes
- Review evidence: `general-purpose` read-only reviewers; Round 1 identified queue-head deletion and missing false-mode guard; final Slice 1 review checked identity consumption and two-round test, final Slice 2 review checked malformed inputs/support level/slot safety. Findings fixed and re-reviewed.
- Review reason: 修改调度器公共任务边界，影响真实设备排班和专精入口。
- Stop conditions: 无法区分 `_mastery` 与普通排班；测试无法证明任务没有被删除。

## Slice 2: 专精开始前验证目标训练位

- Status: completed
- Goal: 目标干员未在训练位时禁止技能选择，并自动恢复推进。
- Scope: 目标解析、实际训练室读取、可重试任务重建和日志。
- Matrix rows: Empty or missing input, Invalid or malformed input, Unavailable or not-ready dependency, Duplicate or idempotent case, Boundary or limit case, Primary path。
- Public behavior: 目标在训练位才点击开始专精；目标不在位时计划保持可推进，按 `plan_key` 去重并以 `now + 5 秒` 重建换班任务；材料不足仍走现有 failed。
- Tests: 目标在位、训练室为空、目标错位、重复执行、缺少目标映射和材料失败；断言不误写 failed、不点击专精、不产生重复任务。
- Implementation notes: 以训练室实际读取为准；复用队列延迟，按 `plan_key` 去重，使用 `now + 5 秒`，避免 transition 内高速循环；不把协助位 `Current` 当目标。
- Verification: `mastery_skill_upgrade_tests` 16/16、`scheduler_task_tests` 14/14、`base_scheduler_tests` 7/7 通过；目标在位成功路径写入有效 `expires_at`，空/错/None/非法槽、读取异常、malformed plan、supports 缺失均不点击且不写 failed。
- Review: required
- Review verdict: PASS after Round 1 and final review fixes
- Review evidence: `general-purpose` read-only reviewers; Round 1 identified supports-empty bypass and malformed test patch; final Slice 2 review checked false-mode guard, level-specific support, retry de-duplication, and test importability. Findings fixed and re-reviewed.
- Review reason: 修改 DB 状态推进与真实 UI 操作前置条件。
- Stop conditions: 排班失败仍永久 failed；依赖过期 Skland 快照；重试重复或无界循环。

## Overall verification

- `uv run --with ruff ruff check ...`: passed
- `uv run --with ruff ruff format --check ...`: passed
- `venv/bin/python -m compileall -q arknights_mower`: passed
- `venv/bin/python -m unittest arknights_mower.tests.scheduler_task_tests`: 14/14 passed
- `HTTP_PROXY=http://127.0.0.1:8118 uv run --with ... python -m unittest arknights_mower.tests.mastery_skill_upgrade_tests arknights_mower.tests.scheduler_task_tests arknights_mower.tests.base_scheduler_tests`: 37/37 passed
- `HTTP_PROXY=http://127.0.0.1:8118 uv run --with ... python -m unittest discover -s arknights_mower/tests -p '*_tests.py'`: 81/81 passed
- Read-only review: required reviews executed with `general-purpose` for both slices; Round 1 findings fixed; final Slice 1 review PASS, final Slice 2 code/test review PASS, and final `tasks.md` cross-check PASS.

- `ruff check .`
- `ruff format --check .`
- `python -m unittest discover -s arknights_mower/tests -p "*_tests.py"`
- 执行 `e2e.md` 中 agent 项目；手机项目仅在用户批准后执行。

## Commit policy

- `rope-go` 完成全部 slices、验证、review 和 issue E2E 状态后，再一次性提交该 issue 的代码与必要文档。
- 不为单个 slice 单独提交；不同 issue 分别提交。
