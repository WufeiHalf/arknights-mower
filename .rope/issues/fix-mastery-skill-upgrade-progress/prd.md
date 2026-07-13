# 修复自动专精任务无法推进

## Problem Statement

在 `assistant_follows_schedule=false` 的默认模式下，`MasterySync` 为专精计划生成的临时训练室换班任务可能被普通训练室排班保护逻辑跳过。随后 `SKILL_UPGRADE` 在空训练室执行，点击训练室主界面的按钮后返回基建，并最终报“未成功进入房间”。专精计划因此无法从 `in_progress(expires_at=NULL)` 推进到真正开始训练的状态。

## Solution

保证专精计划的临时训练室换班任务不会被普通排班保护逻辑误删，并在开始专精前确认目标干员确实位于训练位。目标未在位时不执行专精点击、不把该情况当作材料不足或其他永久失败，而是保留或重建专精换班任务，延迟后自动重试。

## Goals

- 修复 `assistant_follows_schedule=false` 下专精临时换班任务被跳过的问题。
- 只有确认目标干员在训练位后，才允许执行 `SKILL_UPGRADE` 的技能选择流程。
- 区分排班未生效与材料不足、路线缺失等业务失败。
- 保持 `assistant_follows_schedule=true` 的现有语义。
- 为失败路径留下可自动推进的任务状态、日志和回归验证。

## Non-goals

- 不调整训练室按钮坐标，除非回归验证证明坐标仍是独立问题。
- 不修改 `plan.json` 或要求用户把专精目标手动加入普通排班表。
- 不处理材料预检查、Skland API、cultivate.json 刷新或 DB 表结构。
- 不执行未经用户确认的手机部署、服务重启或真实设备写入。

## Public Interface / Behavior

- 用户添加专精计划后，在默认 `assistant_follows_schedule=false` 模式下，Mower 自动安排专精协助位和目标训练干员。
- 专精临时换班任务不会因队列中存在 `SKILL_UPGRADE` 而被普通排班保护逻辑跳过。
- 目标干员未在训练位时，Mower 不点击“开始专精”，而是记录目标、实际训练位和重试原因，并自动保留或重建换班任务。
- 目标干员在训练位且流程正常时，训练开始并写入有效的 `in_progress.expires_at`。
- `assistant_follows_schedule=true` 的普通排班兼容行为保持不变。
- 排班未生效的重试任务使用 `now + 5 秒`，并按 `plan_key` 去重，避免重复任务和高速循环。

## Behavior Contract

- System under test: 专精计划从 `MasterySync` 调度到训练真正开始的训练室排班与 `SKILL_UPGRADE` 协作流程。
- Trigger/input: 数据库存在 pending 专精计划，`MasterySync.sync_and_schedule()` 运行，配置为 false 或 true。
- Collaborators: `MasterySync`、`SchedulerTask` 队列、`agent_arrange_room()`、`choose_train()`、训练室实际干员读取、`mastery_db`。
- Observable result: `_mastery` 临时换班任务被执行；目标干员在训练位后才进入技能选择；成功时 DB 计划有有效 `expires_at`；未在位时队列保留可重试任务且计划不被标记 failed。
- Failure visibility: 日志区分换班被跳过、目标训练位校验失败、材料不足和路线缺失。
- Forbidden shortcuts: 不得只改坐标、只盲点重试、要求改普通 `plan.json`，或把排班未生效直接写成永久 failed。
- Retry contract: 目标未在训练位时，保留 `in_progress` 计划，按 `plan_key` 去重后以 `now + 5 秒` 重建 `_mastery` 任务；不得在当前 transition 内无界重试。

## References

- Spec: `.rope/specs/mastery/application-flow.md`
- Spec: `.rope/specs/phone-deploy/deployment.md`
- ADR: `.rope/adr/0001-phone-dev-branch.md`
- Code: `arknights_mower/utils/mastery_sync.py`
- Code: `arknights_mower/solvers/base_schedule.py`
- Code: `arknights_mower/utils/mastery_db.py`

## Open Questions / Human Gates

- 真实手机验证需要用户明确批准部署、服务重启和观测范围。

## Gate Decisions

- Gate: 手机部署与真实设备专精验证
- Decision: blocked
- Approved action: 用户明确确认后，按 phone/dev 全量流程部署完成 issue 的代码并运行一次受控专精验证。
- Scope: `phone/dev`、指定 ADB 设备、`my-mower-phone/scripts/package-and-push.sh` 及其服务进程。
- Risk: 会覆盖真实设备代码、可能重启服务并改变游戏内排班/专精状态。
- Pass criteria: 目标干员进入训练位；`SKILL_UPGRADE` 成功进入技能选择并开始训练；DB `expires_at` 有效；无“未成功进入房间”。
- Failure report: 提供部署 commit、专精时间线、目标/实际训练位、场景变化、DB 状态和截图。
- Forbidden out-of-scope actions: 未确认不得部署、单文件覆盖、重启服务、重置或删除 DB 专精计划。
