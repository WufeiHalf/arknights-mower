# 修复自动专精任务无法推进 E2E

## E1 Local regression and diagnostics

Executor: agent
Risk: local-readonly
Gate Decision: not-required
Approved Action: N/A
Scope: 本仓库变更模块与相关测试
Command or Steps:
- 运行 targeted mastery/scheduler tests。
- 运行 `ruff check .`、`ruff format --check .`。
- 运行 `python -m unittest discover -s arknights_mower/tests -p "*_tests.py"`。
Pass Criteria:
- false 模式下 `_mastery` 不被跳过。
- 空/错训练位阻止专精点击，并按 `plan_key` 去重、以 `now + 5 秒` 保留可重试任务而不写 `failed`。
- true 模式与普通排班测试通过。
Failure Report:
- 报告命令、失败测试、任务队列和日志断言。
Forbidden Out-of-Scope Actions:
- 不部署手机、不重启服务、不重置 DB。
Result:
- agent_passed: targeted `HTTP_PROXY=http://127.0.0.1:8118 HTTPS_PROXY=http://127.0.0.1:8118 ALL_PROXY=http://127.0.0.1:8118 uv run --with scikit-image --with opencv-python-headless --with pytz --with tzlocal --with requests --with pyyaml --with pydantic --with yamlcore --with colorlog --with scikit-learn --with jinja2 --with cryptography --with pandas --with evalidate --with rapidocr-onnxruntime --with beautifulsoup4 --with ruff python -m unittest arknights_mower.tests.mastery_skill_upgrade_tests arknights_mower.tests.scheduler_task_tests arknights_mower.tests.base_scheduler_tests`: 37/37 passed.
- agent_passed: full `HTTP_PROXY=http://127.0.0.1:8118 HTTPS_PROXY=http://127.0.0.1:8118 ALL_PROXY=http://127.0.0.1:8118 uv run --python /usr/bin/python3.12 --with-requirements requirements.txt --with ruff python -m unittest discover -s arknights_mower/tests -p '*_tests.py'`: 81/81 passed.
- agent_passed: Ruff lint/format, `venv/bin/python -m compileall -q arknights_mower`, and `git diff --check` passed. Python 3.13 full-dependency resolution was skipped because `onnxruntime==1.18.1` has no `cp313` wheel; the same full suite passed under the repository's Python 3.12 requirement.

## E2 Issue document consistency

Executor: agent
Risk: local-readonly
Gate Decision: not-required
Approved Action: N/A
Scope: issue 包、`AGENTS.md`、相关 mastery/phone specs
Command or Steps:
- 运行 `git diff --check`。
- 检查 Behavior Matrix 覆盖与 gate 决策。
Pass Criteria:
- 无 whitespace 错误。
- PRD、tasks、E2E 和 AGENTS 术语一致。
- 手机部署保持 blocked，未被默认为可执行。
Failure Report:
- 列出文档、矩阵或 gate 不一致。
Forbidden Out-of-Scope Actions:
- 不修改实现代码。
Result:
- agent_passed: `git diff --check` passed; Behavior Matrix and gate decisions reviewed; no whitespace errors.

## E3 Deploy completed issue to phone

Executor: agent-with-gate
Risk: production
Gate Decision: blocked
Approved Action: 用户明确确认后，将完成 issue 的 issue-level commit 按 phone/dev 全量流程部署到指定手机，并重启验证所需的 mower 服务。
Scope: `phone/dev`、`/home/wufei/Desktop/privatecode/my-mower-phone`、ADB 设备 `2c42067`、手机 mower 服务和运行文件
Command or Steps:
- 执行前展示 issue-level commit 与部署 diff。
- 获得明确确认后使用全量部署脚本，禁止单文件复制。
- 验证手机源码来自批准的 issue-level commit。
- 仅在另行批准状态重置后运行一次受控专精任务。
Pass Criteria:
- 从批准 commit 完成部署。
- phone-only patches 未丢失。
- 未修改无关服务或数据。
Failure Report:
- 报告部署输出、源码/commit 验证、服务状态和运行时变化。
Forbidden Out-of-Scope Actions:
- 未确认不得执行；不得单文件覆盖、clean/reset、删除 DB 或无批准重启服务。
Result:
- blocked_on_gate: deployment requires explicit user confirmation; no package-and-push, ADB write, service restart, DB reset, or real-device verification executed.

## E4 Real-device mastery acceptance

Executor: user
Risk: human-judgment
Gate Decision: user-run
Approved Action: 在批准的手机运行中观察一个自动专精计划，确认目标干员进入训练位并开始训练。
Scope: 已批准手机会话和选定专精计划
Command or Steps:
- 确认游戏在前台且计划为 pending。
- 观察 `_mastery`、`SKILL_UPGRADE`、`building_training` 日志和截图。
- 确认目标干员在技能选择前已位于训练位。
- 确认倒计时出现，DB `expires_at` 非空。
Pass Criteria:
- 目标实际进入训练位。
- 不因空房间返回基建。
- 倒计时开始且无“未成功进入房间”。
Failure Report:
- 提供带时间戳日志、训练室截图、目标/实际干员、场景序列和 DB 历史。
Forbidden Out-of-Scope Actions:
- 不改无关排班，不手动改 DB。
Result:
- blocked_on_user: real-device acceptance remains for user-run validation after an approved deployment.
