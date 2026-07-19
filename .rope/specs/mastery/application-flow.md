# Mastery Application Flow

## Scope

The full automatic mastery (专精) pipeline: from user adding a plan
to training completion. Covers `MasterySync`, `skill_upgrade`,
`refresh_skill_time`, and the DB state machine.

## Components

- **mastery_db.py**: `mastery_plan` table. State machine:
  `pending -> in_progress -> completed|failed`. Each state change
  inserts a new row (append-only); queries take `MAX(id)` per
  `(char_id, skill_index)`.
- **mastery_sync.py**: `MasterySync.sync_and_schedule()` -- runs in
  `infra_main`'s `todo_task` stage. Refreshes Skland data, syncs DB,
  schedules pending plans.
- **base_schedule.py**:
  - `infra_main()`: task consumer + MasterySync trigger
  - `skill_upgrade(skill)`: the training room state machine
  - `refresh_skill_time()`: reads training countdown, handles completion
  - `_handle_training_complete()`: marks plan completed + adds next level

## Full Flow

```
User adds plan (WebUI POST /mastery-plan)
  └-> DB: insert pending(level=1)

infra_main -> todo_task stage -> MasterySync.sync_and_schedule()
  ├─ Refresh Skland (cultivate().start())
  ├─ Check in_progress plan:
  │   ├─ trainee matches -> update expires_at -> add REFRESH_TIME -> return
  │   ├─ trainee mismatch -> mark failed
  │   └─ trainee=None -> mark failed (断点C, see below)
  ├─ _auto_complete_level3 (cultivate.json already-done levels)
  └─ pending exists -> _schedule_next:
      ├─ DB: pending -> in_progress (expires_at=NULL)
      ├─ Select support by target plan level, not route-list position
      ├─ If the previous level's swap assistant is still present, enqueue
      │  {train: [Current, trainee]} so its next-training effect is consumed
      ├─ Otherwise enqueue {train: [level_support, trainee]} meta=_mastery
      └─ Enqueue: SKILL_UPGRADE {meta: "name 技能N"}

infra_main consumes queue:
  ├─ 上班任务 -> agent_arrange -> support+trainee enter train room
  └─ SKILL_UPGRADE -> skill_upgrade("name 技能N"):
      tasks = ["collect", "upgrade", "confirm"]
      自动计划的目标等级来自 mastery_plan.level，不从倒计时反推
      ├─ collect: 收取上次训练结果 (training_idle -> skip, training_completed -> tap)
      ├─ upgrade: 进技能选择 -> 选技能 -> 确认
      └─ confirm: 读倒计时 -> set_plan_status(in_progress, expires_at)
                    ↑ 训练真正开始
                    └─ 成功后才按当前等级创建协助位换人任务

refresh_skill_time (REFRESH_TIME task):
  ├─ 训练完成 -> _handle_training_complete -> completed (+pending next level)
  │                不直接创建 SKILL_UPGRADE；由下一次 MasterySync 统一调度
  └─ 未完成 -> 更新expires_at + _calculate_swap_from_api
```

## Mid-swap Contract (减半换人)

`_calculate_swap_from_api` must select the route entry by **current
`mastery_plan.level`**, never by matching the Skland trainer name.

- L1/L2 with `swap=true`: schedule `{train: [swap_name, Current]}`
- L3 with `swap=false`: never schedule mid-swap, even if snapshot still
  shows a previous-level assistant (e.g. 罗宾 after L2)
- Specialty full flow (example):
  - L1: 罗宾 start → mid-swap 逻各斯
  - L2: keep 逻各斯 start → put 罗宾 → mid-swap 逻各斯
  - L3: keep 逻各斯 start → put 望 → no mid-swap

Reason: Skland `building_training` can lag across level boundaries;
matching by trainer name reuses the previous level's `swap` flag and
incorrectly demotes L3 assistants like 望 to 逻各斯.

## DB State Machine

```
pending ──_schedule_next──> in_progress(expires_at=NULL)
                               │
                          skill_upgrade confirm
                               │
                    in_progress(expires_at=<time>)
                               │
                     refresh_skill_time 到期
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
              completed              failed
              (level<3:              (训练中断/
               +pending next)         材料不足/
                                       未进房间)
```

## Known Breakpoints (as of 2026-07-12)

### 断点A: MasterySync 不检查材料就调度

`_schedule_next` sees pending -> immediately schedules. Does not check
whether WORKSHOP tasks are still running or materials are ready.

**Impact**: Training scheduled before materials synthesized.
**Status**: Not yet fixed. Need to gate on WORKSHOP queue or material
readiness.

### 断点B: skill_upgrade training_idle return (FIXED)

`skill_upgrade` collect stage saw `training_idle` and `return`-ed,
skipping upgrade+confirm. Training never started but SKILL_UPGRADE
task was consumed.

**Root cause**: PR #875 added `return` to avoid OCR misreading the
empty timer. But `return` exits the whole function, not just the OCR.

**Fix** (commit c4093e8c): `continue` instead of `return`. `del tasks[0]`
removes "collect", then `continue` skips the OCR `double_read_time`
call and re-enters the loop with `tasks[0]="upgrade"`.

```python
# Wrong
if self.find("training_idle"):
    del tasks[0]
    return          # 训练从未开始

# Correct
if self.find("training_idle"):
    del tasks[0]
    continue        # 跳过 OCR，循环重进走 upgrade
```

### 断点C: in_progress 被 MasterySync 误杀 (FIXED)

`_schedule_next` marks `in_progress(expires_at=NULL)` immediately, but
training doesn't physically start until `skill_upgrade` confirm stage
sets `expires_at`. In between, MasterySync may run again, read stale
`player_info_cache` (from a prior successful fetch when training room was
empty, so `trainee=None`), and mark `failed`.

Also triggered by transient Skland DNS failures: `_refresh_skland_data()`
throws, but `sync_and_schedule` continues and reads the stale cache.

**Impact**: Plan killed before training starts; even worse, when Skland
is unreachable, a new pending plan may be scheduled and evict an
operator already in training (because MasterySync doesn't know the
training room state without Skland).

**Fix** (commit 062a33a5): Introduced `skland_ok` flag. When
`_refresh_skland_data()` fails:

- Skip in_progress validation (keep plan alive, rely on in-game
  `refresh_skill_time` to drive completion)
- Skip pending scheduling entirely (don't risk evicting an operator
  in training)

```python
skland_ok = True
try:
    self._refresh_skland_data()
except Exception as e:
    skland_ok = False

if plan and not skland_ok:
    # skip validation, keep plan
elif plan:
    # normal Skland-based validation

if not skland_ok:
    # don't schedule pending (could evict training operator)
    return
```

**Trade-off**: Skland long-unreachable stalls new pending plans. But
existing in_progress plans still advance via `refresh_skill_time`.
Recovers automatically when Skland comes back.

## Mastery Room Retry Contract

A failed plan must retain its target `level`. For legacy material failures that
were stored with the default `level=1`, `retry_plan()` recovers the target from
the `failed_reason="材料不足 levelN"` suffix before inserting the new pending row.

In `assistant_follows_schedule=false` mode, the `_mastery` temporary
training-room task created by `MasterySync` must run before its
`SKILL_UPGRADE` task. If the post-arrangement room read does not find the
target operator in the training slot:

- Do not tap the TRAIN_MAIN start-specialization button.
- Do not mark the plan as material failure or permanent `failed`.
- Keep the `in_progress` plan and rebuild one `_mastery` task after
  de-duplicating by `plan_key`.
- Schedule the retry at `now + 5 seconds`; do not spin inside the current
  transition.
- Continue to `SKILL_UPGRADE` only after the target operator is confirmed
  in the training slot.

The ordinary training-room protection must not delete a task with
`meta_data="_mastery"`. The `assistant_follows_schedule=true` behavior,
where the assistant slot follows the ordinary schedule, remains unchanged.

## Inventory Data Is Not Real-Time

`cultivate.json` (Skland API snapshot) and `inventory` table (DepotSolver
scan) are **not** updated after `craft_material` completes. `generate_product`
calls `cultivate().start()` at the *start* of each workshop task, so
materials produced in prior tasks are visible to the next. But
`try_workshop_tasks` (in `plan_solver`) reads `inventory` table which
may be stale.

This means `try_workshop_tasks` may skip workshop tasks for operators
whose materials were just produced, because the inventory table hasn't
been refreshed.

## MasterySync Trigger Conditions

MasterySync runs in `infra_main`'s `elif not self.todo_task:` branch
(line ~655). This branch fires only when:

1. `self.planned == True` (plan_solver ran)
2. `self.todo_task == False` (not yet done)
3. No pending task within the window checked by `no_pending_task`

If workshop tasks are densely packed (every 10 min), MasterySync may
fire between them.

## Tests Required

- Mastery scheduling regression: false 模式下 `_mastery` 不被普通训练室保护逻辑跳过；目标训练位为空或错位时不点击专精，按 `plan_key` 去重并以 `now + 5 秒` 重试；true 模式保持兼容。

## Key Files

- `arknights_mower/utils/mastery_db.py`: DB CRUD
- `arknights_mower/utils/mastery_sync.py`: `MasterySync` class
- `arknights_mower/utils/mastery_recommendation.py`: route computation,
  `compute_workshop_config`, `_supports_from_dicts`
- `arknights_mower/solvers/base_schedule.py`: `infra_main`,
  `skill_upgrade`, `refresh_skill_time`, `_handle_training_complete`
- `server.py`: `/mastery-plan`, `/workshop-auto-config` routes
- `ui/src/pages/MasteryRecommendation.vue`: WebUI
