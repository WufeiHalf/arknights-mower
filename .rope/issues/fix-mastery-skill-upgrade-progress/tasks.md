# 修复自动专精任务无法推进 Tasks

## Behavior Matrix

| Row | Applies? | Verification |
| --- | --- | --- |
| Primary path | yes | Slice 1 + Slice 2；E2/E3 |
| Alternate input or entrypoint | yes | MasterySync 调度与完成后下一级入口 |
| Empty or missing input | yes | 空训练室不得点击专精，进入重试 |
| Invalid or malformed input | yes | 缺少目标映射时保持可见失败，不误删无关排班 |
| Unavailable or not-ready dependency | yes | 训练位识别/排班未生效时保留重试；Skland 沿用断点 C |
| Duplicate or idempotent case | yes | 目标已在位不重复换人；不生成重复 `_mastery` |
| Boundary or limit case | yes | true/false 配置、两训练位、`Current` 协助位 |
| Existing behavior compatibility | yes | true 模式与普通非训练室排班不回归 |
| Real entrypoint or integration path | yes | `infra_main` 消费队列；手机验证需门禁 |

## Slice 1: 保护专精临时换班任务

- Status: completed
- Goal: `meta_data="_mastery"` 的训练室换班任务在 false 模式正常执行。
- Scope: 普通训练室排班保护条件与任务身份判定。
- Matrix rows: Primary path, Alternate input or entrypoint, Duplicate or idempotent case, Boundary or limit case, Existing behavior compatibility。
- Public behavior: 队列同时存在 `_mastery` 和 `SKILL_UPGRADE` 时，前者仍进入 `agent_arrange_room()`/`choose_train()`；普通训练室排班仍受保护；true 模式不变。
- Tests: 任务队列与 `agent_arrange_room()` 行为测试，验证 `_mastery` 不被删除、普通任务仍受保护、true/false 分支不混淆。
- Implementation notes: 复用已有 `SchedulerTask` 任务身份，不新增平行状态机。
- Verification: Ruff lint/format、compileall、scheduler_task_tests 14/14 通过；目标 mastery 测试因环境缺少 `skimage` 未能导入执行。真实 `agent_arrange_room()` 路径已补回归测试。
- Review: required
- Review verdict: approved after read-only review fixes
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
- Verification: Ruff lint/format、compileall、git diff --check、scheduler_task_tests 14/14 通过；mastery 回归与全量 unittest 受缺失 `skimage`/模型依赖阻塞。读取异常、空槽、错位、去重、now+5s 重建和不写 failed 已覆盖测试。
- Review: required
- Review verdict: approved after read-only review fixes
- Review reason: 修改 DB 状态推进与真实 UI 操作前置条件。
- Stop conditions: 排班失败仍永久 failed；依赖过期 Skland 快照；重试重复或无界循环。

## Overall verification

- `uv run --with ruff ruff check ...`: passed
- `uv run --with ruff ruff format --check ...`: passed
- `venv/bin/python -m compileall -q arknights_mower`: passed
- `venv/bin/python -m unittest arknights_mower.tests.scheduler_task_tests`: 14/14 passed
- `venv/bin/python -m unittest discover ...`: blocked by missing `skimage` and model dependency imports; no changed-test assertion failure observed
- Read-only review: approved after two review rounds and fixes

- `ruff check .`
- `ruff format --check .`
- `python -m unittest discover -s arknights_mower/tests -p "*_tests.py"`
- 执行 `e2e.md` 中 agent 项目；手机项目仅在用户批准后执行。

## Commit policy

- `rope-go` 完成全部 slices、验证、review 和 issue E2E 状态后，再一次性提交该 issue 的代码与必要文档。
- 不为单个 slice 单独提交；不同 issue 分别提交。
