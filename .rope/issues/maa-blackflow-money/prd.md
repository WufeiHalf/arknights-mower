# 集成战略：黑流树海刷钱（牛杂）

## Problem Statement

MAA 上游在"牛杂"（MiniGame）模块通过资源 OTA 下发了新集成战略「沉沦者的黑流树海」的刷钱入口（`BlackFlowTemporary` 任务链：选分队→招募→行动力→投资存钱→钱满重开）。mower 目前大型任务只支持肉鸽（RG）/保全（SSS）/生息演算（RCL）/生息演算自跑（RA）/隐秘战线（SF），无法调用这个新刷钱功能。用户希望 mower 大型任务里新增"黑流树海刷钱"，由 mower 自动导航到黑流树海"开始探索"界面后交给 MAA 刷钱。

## Solution

在大型任务框架（`maa_plan_solver`）新增类型 `bf`（BlackFlow）：

1. **conf 新增**：`conf.BF` 属性（`maa_rg_enable == 1 and maa_long_task_type == "bf"`），与 RG/SSS/RCL/RA/SF 同构
2. **启动前预检**：`MAA ≥ v6.14.0`（解析 `Asst().get_version()`）+ 本地 tasks.json 含 `BlackFlowTemporary@Begin` 任务；不满足则报错退出并提示升级 MAA/更新资源
3. **自动导航 `to_blackflow`**：参照 `to_reclamation` 范式——终端 → 长期探索 → 集成战略入口 → 黑流树海主题页 → 停在"开始探索"界面（右下角开始探索按钮可见），然后交给 MAA
4. **MAA 调用**：`append_task("Custom", {"task_names": ["BlackFlowTemporary@Begin"]})`（已验证 MaaCore `CustomTask` 契约）
5. **触发/停止**：复用 RG 时间窗（`maa_rg_sleep_min/max`）+ 现有大型任务循环（任务时间点/stop_maa 停止，不自动重启）
6. **前端**：`LongTasks.vue` 类型下拉加 `bf` 选项（"黑流树海刷钱 (Maa)"）

## Goals

- mower 大型任务支持 `maa_long_task_type = "bf"` 跑黑流树海刷钱
- mower 自动导航到黑流树海"开始探索"界面（全自动，不要求用户手动停界面）
- 启动前预检 MAA 版本 + 任务链可用性，失败给出明确报错
- 与现有大型任务（RG/SSS/RCL）共用调度节奏与停止逻辑

## Non-goals

- 不实现黑流树海正式主题适配（MAA 上游 `theme:"BlackFlow"` 未合入，等上游 PR #17380/#17481 转正后再评估）
- 不写 mower 自己的刷钱逻辑（投资/重开全部由 MAA 任务链完成）
- 不处理 MAA 任务运行中卡死/报错的重启（沿用现有循环：只记录，不自动重启）
- 不做手机端 MAA 升级/资源更新（属用户操作，预检只提示）

## Public Interface / Behavior

### 配置（`utils/config/conf.py` `LongTaskPart`）

- `conf.BF` 属性：`maa_rg_enable == 1 and maa_long_task_type == "bf"`

### 后端（`solvers/base_schedule.py` `maa_plan_solver`）

- `if (conf.RG or conf.SSS or conf.RCL or conf.BF) and not rg_sleep:` 进入大型任务循环
- `elif conf.BF:` 分支：预检 → `to_blackflow()` 导航 → `append_task("Custom", {"task_names": ["BlackFlowTemporary@Begin"]})` → `MAA.start()` → 现有 running 循环

### 预检（新函数，`solvers/base_schedule.py` 或 utils 新模块）

- 输入：`maa_path`、本地 tasks.json（`<maa_path>/cache/resource/tasks.json`）
- 检查项：
  - MAA 版本 ≥ v6.14.0（`Asst().get_version()` 解析，如 "v6.14.2" → (6,14,2)）
  - tasks.json 含 `BlackFlowTemporary@Begin` key（JSON 顶层）
- 输出：失败时 `raise Exception` 带明确中文提示（"黑流树海刷钱需要 MAA ≥ v6.14.0，当前 x.y.z" / "MAA 资源未包含 BlackFlowTemporary 任务链，请更新 MAA 资源"）

### 导航 `to_blackflow`（`utils/solver.py`，参照 `to_reclamation`）

- 入口：`self.scene()` 当前场景
- 路径：`Scene.INDEX` → `tap_index_element("terminal")` → `Scene.TERMINAL_MAIN` → `tap_terminal_button("longterm")` → `Scene.TERMINAL_LONGTERM` → 点集成战略入口（新模板 `bf/integrated_strategy`）→ 主题页 → 点黑流树海主题（新模板 `bf/blackflow_theme`）→ 停在"开始探索"界面（校验模板 `bf/start_explore` 或 OCR"开始探索"）
- 超时：参照 `to_reclamation`（每个阶段超时报错）
- 模板缺失：日志 warning + 尝试继续（占位先行，Slice 3 补真实模板）

### 前端（`ui/src/components/LongTasks.vue`）

- `maa_long_task_options` 加 `{ label: '黑流树海刷钱 (Maa)', value: 'bf' }`
- 无额外配置项（复用 RG 时间窗）

## Testing Decisions

- Good test: 观察 conf 属性、预检函数的纯逻辑行为 + `maa_plan_solver` 分派行为——不测设备交互
- Seams under test:
  1. **conf 属性 seam**：`conf.BF` 真值表（`maa_rg_enable` × `maa_long_task_type`）——MagicMock conf 单测
  2. **预检 seam**：版本解析纯函数（"v6.14.2"、"6.14.2"、旧版、非法）+ tasks.json 任务存在性检查——纯函数单测
  3. **分派 seam**：`maa_plan_solver` 在 `conf.BF` 时调用 `to_blackflow` + `append_task("Custom", {"task_names": [...]})`——patch `BaseSchedulerSolver.__init__`/`MAA` 单测
- Prior art: `arknights_mower/tests/maa_check_tests.py`（patch conf 单测）、`arknights_mower/tests/base_scheduler_tests.py`（patch `__init__` 单测 solver 方法）

## Behavior Contract

- System under test: mower 大型任务对"黑流树海刷钱"（`bf` 类型）的支持
- Trigger/input: `conf.yml` 设置 `maa_rg_enable: 1`、`maa_long_task_type: "bf"`，到达 `maa_rg_sleep_min/max` 时间窗，`maa_plan_solver` 进入大型任务分支
- Collaborators: MAA（≥v6.14.0 + 资源含 BlackFlowTemporary 任务链，`Asst.load(incremental_path=cache)` 加载 OTA tasks.json）、游戏客户端（已解锁黑流树海主题）、mower 场景识别（终端/长期探索/集成战略/黑流树海主题）
- Observable result: 游戏进入黑流树海"开始探索"界面，MAA 开始跑 `BlackFlowTemporary@Begin` 任务链（日志出现任务链执行/投资相关输出），循环到任务时间点或 stop_maa 停止
- Failure visibility: 预检失败（版本不足/任务链缺失）→ 明确中文报错 + `send_message` 通知 + 不进入 MAA 循环；导航超时 → 报错 + 邮件/消息通知（同 `to_reclamation` 行为）；模板缺失 → 日志 warning（Slice 2 占位期）
- Forbidden shortcuts:
  - 不通过 `theme:"BlackFlow"` 标准 Roguelike 调用（上游未合入，会静默失败）
  - 不写 mower 自己的点击脚本模拟刷钱（必须走 MAA Custom 任务链）
  - 不做"用户手动停在开始探索界面再启动"的半自动方案（需求已定全自动）
  - 预检不通过时不允许继续执行（防止空转）

## References

- Research: `.rope/research/maa-blackflow-money.md`
- Spec: `.rope/specs/phone-deploy/deployment.md`（phone/dev 部署模型）、`.rope/specs/phone-deploy/asst-path-priority.md`（asst 路径优先级）

## Open Questions / Human Gates

- 手机端 MAA 实际版本与资源更新状态未验证（用户确认手机为最新版，但 BlackFlowTemporary 可用性需上机确认）——E2E 覆盖
- 黑流树海主题游戏内解锁状态未验证（需账号已解锁该主题）——E2E 覆盖
- 游戏截图素材（导航模板）由用户主力手机提供，时间待定——Slice 3 前置
- 导航模板跨分辨率可用性（ORB 匹配 0.8~1.25 缩放窗口）需上机校准——E2E 覆盖

## Gate Decisions

- Gate: 手机端 MAA 能力验证（E1）
- Decision: user-run
- Approved action: 用户在手机端确认 MAA ≥ v6.14.0、资源已更新（MAA GUI 牛杂-黑流树海刷钱入口可见/可跑）
- Scope: 手机端 MAA GUI（非 mower 代码）
- Risk: BlackFlowTemporary 是 OTA 临时下发资源，手机端资源未更新则任务链缺失
- Pass criteria: 手机端 MAA 牛杂模块能看到"黑流树海刷钱"入口且手动跑通一轮
- Failure report: 手机端 MAA 版本号、牛杂入口是否可见、报错信息
- Forbidden out-of-scope actions: 不在手机上执行任何 mower 部署或写操作

- Gate: 手机端 mower 上机验证（E2）
- Decision: user-run
- Approved action: 用户在家时在手机端跑一次 `bf` 大型任务，观察导航到"开始探索"界面 + MAA 刷钱启动
- Scope: phone/dev 部署的手机环境
- Risk: 真实设备写操作（部署 + 游戏操作）
- Pass criteria: mower 自动导航到黑流树海"开始探索"界面，MAA 任务链开始执行，日志无预检/导航报错
- Failure report: 日志文件、卡在哪个场景、报错内容
- Forbidden out-of-scope actions: 不在验证外修改手机端配置、不跑其他大型任务
