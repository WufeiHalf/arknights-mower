# ADR 0002: Remove the skill_upgrade entry guard, adopt upstream semantics

- Status: Accepted (2026-09-13, commit 82e042cda)
- Supersedes: the entry-guard half of the Mastery Room Retry Contract in
  `specs/mastery/application-flow.md` (level retention in `retry_plan` stays)
- Context: upstream merge 2026-09 (#902/#903/#904/#906, merge 36dd64115)

## Context

Two halves of the mastery pipeline made opposite assumptions about when a
`mastery_plan` row transitions `pending -> in_progress`:

| | Local (PR #891/#893 era) | Upstream #902 |
|---|---|---|
| At scheduling | `_schedule_next` marks `in_progress(expires_at=NULL)` upfront | No status change; plan stays pending |
| At skill_upgrade entry | Hard guard: `_mastery_context(plan_key)` requires `status='in_progress'` (else WARNING + silent skip) | No guard; executes unconditionally on whatever is in the training room |
| At confirm | Sets `expires_at` | Sets `in_progress` + `expires_at` (deferred marking) |
| Self-consistency | Guard works because scheduling pre-marked | Guard absent, so deferred marking is safe |

Each side is internally consistent. The 2026-09 upstream merge kept BOTH the
deferred marking (upstream) and the entry guard (local). The combination
deadlocks:

```
pending plan -> _schedule_next (queue only, no DB change)
  -> train arrange task + SKILL_UPGRADE
  -> skill_upgrade entry: get_in_progress_plan() -> None (still pending)
  -> "invalid mastery plan_key" -> return
  -> plan still pending -> next sync_and_schedule -> schedule again -> loop
```

Observed 2026-09-13 21:16–21:41 (乌尔比安 S2): 29 re-schedules, 28 skip
warnings, training-room operators re-arranged every 20–40s. Training never
started.

## Decision

Adopt upstream semantics wholesale for `skill_upgrade`:

1. Delete the entry guard block and its 6 helpers
   (`_mastery_context`, `_mastery_target_name`,
   `_mastery_target_in_training_room`, `_mastery_support_for_plan`,
   `_requeue_mastery_upgrade`, `_retry_mastery_arrangement`).
2. Division of responsibility = upstream's: the schedule task is responsible
   for putting the right operators in the training room; `skill_upgrade` is
   responsible for executing (collect/upgrade/confirm) without re-checking.
3. TRAIN_SKILL_UPGRADE level inference returns to OCR remaining-time
   (>23h→3, >15h→2, else 1); the DB plan-level priority is dropped with the
   guard.

Rationale: the guard protected a low-frequency failure (arrange task failed
to seat the target) at the cost of a fragile implicit contract that broke on
the first upstream semantic change. Upstream runs at scale without the guard.
Smaller diff = cheaper future merges and a smaller PR #891 integration
surface.

## Consequences

Accepted risks:

- If an arrange task fails silently, skill_upgrade may start training on the
  wrong operator/skill (materials + time wasted, DB row then describes
  training that belongs to another operator). Practically rare; detected by
  the next Skland sync (trainee mismatch -> failed) or human inspection.
- Half-duration OCR jitter can record level 1 for a level-3 training in
  progress (e.g. 12h remaining on a 24h course). Affects DB level display and
  downstream level checks; upstream lives with this.

Kept local deviations (do NOT "fix" to upstream without reading this):

- `expires_at` is written in **local time** (`execute_time.strftime`). Upstream
  writes UTC while the DB expiry check compares with
  `datetime('now','localtime')` -- following upstream would expire every
  in_progress plan 8 hours early (CST). Guarded by
  `test_update_expires_at_uses_local_database_time`.
- Manual-task rule stays: all mastery entry points must POST /mastery-plan
  first (see application-flow.md "Manual Task Contract") -- not because of the
  removed guard, but because completion progression and restart survival
  require a DB row.

PR #891 note: if upstream ever adopts the plan_key context work, it must
reconcile this hand-off point explicitly (deferred marking + any entry-time
context lookup); merging #891 as-is onto #902 would reintroduce this deadlock.
