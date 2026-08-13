# 集成战略：黑流树海刷钱（牛杂） Tasks

## Behavior Matrix

| Row | Applies? | Verification |
| --- | --- | --- |
| Primary path | yes | Slice 2 - `conf.BF` 时导航 + append Custom 任务链 |
| Alternate input or entrypoint | yes | Slice 1 - `conf.BF` 真值表（rg_enable 0/1 × type bf/其他） |
| Empty or missing input | yes | Slice 1 - tasks.json 缺失/为空、version 解析失败 |
| Invalid or malformed input | yes | Slice 1 - version 字符串非法格式、tasks.json 非 JSON |
| Unavailable or not-ready dependency | yes | Slice 1 - MAA 版本 < v6.14.0、tasks.json 缺 BlackFlowTemporary@Begin |
| Duplicate or idempotent case | yes | Slice 2 - 大型任务循环内 BF 分支不重复 append（每次 initialize_maa 后 append 一次） |
| Boundary or limit case | yes | Slice 1 - 版本恰好 v6.14.0（≥ 通过） |
| Existing behavior compatibility | yes | Slice 2 - RG/SSS/RCL/RA/SF 分支行为不变（conf.BF 为 False 时不走新分支） |
| Real entrypoint or integration path | yes | Slice 3 - 手机端上机验证导航 + 刷钱启动 |

## Slice 1: conf.BF 属性 + 启动预检

- Status: done
- Kind: vertical
- Verification result: `venv/bin/python -m unittest discover -s arknights_mower/tests -p "*_tests.py"` → Ran 131 tests OK; ruff check/format OK
- Review verdict: PASS（reviewer 提出 alpha/beta 版本后缀误报问题 → 已修复 c2e1316d7）
- Review notes: `parse_maa_version` 原只接受 3 段，alpha/beta 通道（"v6.16.9-alpha.1.d013..."）误抛 ValueError；修复后取前 3 段数字、不足 3 段仍报错
- Goal: 用户配置 `maa_long_task_type: "bf"` 后 mower 能识别该类型，并在启动刷钱前验证 MAA 能力（版本 + 任务链存在性），不满足时给出明确报错
- Blocked by: none
- Scope: `arknights_mower/utils/config/conf.py`（LongTaskPart 加 `BF` 属性）、新预检函数（`utils/maa_check.py` 或 `solvers/base_schedule.py` 内，可单测的纯函数）、`arknights_mower/tests/`（新 `blackflow_precheck_tests.py`）
- Matrix rows: Primary path、Alternate input or entrypoint、Empty or missing input、Invalid or malformed input、Unavailable or not-ready dependency、Boundary or limit case
- Public behavior: 设置 `maa_rg_enable: 1` + `maa_long_task_type: "bf"` 后，`conf.BF` 为 True；预检函数能判断 MAA 版本是否 ≥ v6.14.0 且本地 tasks.json 含 `BlackFlowTemporary@Begin`，失败时返回含明确中文提示的错误
- Tests:
  - `conf.BF` 真值表：`(rg_enable, type)` 组合 → `(1,"bf")=True`、`(0,"bf")=False`、`(1,"rogue")=False`
  - 版本解析：`"v6.14.2"→(6,14,2)`、`"6.14.2"→(6,14,2)`、`"v6.14.0"→通过`、`"v6.13.9"→不通过`、非法串→错误
  - tasks.json：含 `BlackFlowTemporary@Begin`→通过；缺失→错误；非 JSON/空文件→错误
- Implementation notes:
  - 预检函数签名建议：`check_blackflow_prereqs(maa_path) -> None`（失败 raise Exception 带中文提示），内部读 `<maa_path>/cache/resource/tasks.json`（mower OTA 已拉取的位置）；版本从 `Asst().get_version()` 获取（注意预检在 `initialize_maa` 之后调用，MAA 已连接）
  - 版本解析提为纯函数 `parse_maa_version(version_str) -> tuple[int,int,int]` 便于单测
- Verification: `python -m unittest discover -s arknights_mower/tests -p "*_tests.py"` 通过 + `ruff check .` / `ruff format --check .` 通过
- Review: required
- Review reason: conf 属性变更 + 预检失败路径影响用户体验（报错文案需确认）

## Slice 2: maa_plan_solver 分派 + to_blackflow 导航

- Status: done
- Kind: vertical
- Verification result: `venv/bin/python -m unittest discover -s arknights_mower/tests -p "*_tests.py"` → Ran 140 tests OK; ruff check/format OK; `npm run build` OK
- Review verdict: PASS（reviewer 提出高严重度问题：resources/bf/ 不存在时 find 抛 FileNotFoundError 而非返回 None，占位行为真机不可达 → 已修复 078f64b1f，新增模板缺失容错测试）
- Review notes: `find_template` 包装捕获 OSError→warning+继续；start_explore 缺失时轮询到 2min 超时（超时 raise 不被吞）
- Goal: 时间窗内 `conf.BF` 时 mower 自动导航到黑流树海"开始探索"界面并启动 MAA 刷钱任务链，循环/停止与现有大型任务一致
- Blocked by: Slice 1
- Scope: `arknights_mower/solvers/base_schedule.py`（`maa_plan_solver` 大型任务循环加 `conf.BF` 条件 + `elif conf.BF:` 分支）、`arknights_mower/utils/solver.py`（新增 `to_blackflow`，参照 `to_reclamation` L740）、`ui/src/components/LongTasks.vue`（类型下拉加 `bf` 选项）、`arknights_mower/tests/base_scheduler_tests.py`（分派测试）
- Matrix rows: Primary path、Duplicate or idempotent case、Existing behavior compatibility、Real entrypoint or integration path
- Public behavior: 配置 `bf` 类型后，到达时间窗 mower 自动：预检 → 导航到黑流树海"开始探索"界面 → `append_task("Custom", {"task_names": ["BlackFlowTemporary@Begin"]})` → MAA 开始执行；RG/SSS/RCL 行为不变
- Tests:
  - 分派：patch `BaseSchedulerSolver.__init__`，`conf.BF=True` 时 `maa_plan_solver` 调用 `to_blackflow()` + `MAA.append_task` 收到 `("Custom", {"task_names": ["BlackFlowTemporary@Begin"]})`
  - 兼容：`conf.RG=True` 时仍走原 Roguelike 分支（BF 分支不触发）
  - 导航函数存在性 + 超时路径：`to_blackflow` 在场景不匹配时抛错/超时（patch scene 序列）
- Implementation notes:
  - `to_blackflow` 阶段：INDEX→terminal→TERMINAL_MAIN→longterm→TERMINAL_LONGTERM→集成战略入口（模板 `bf/integrated_strategy`）→黑流树海主题（模板 `bf/blackflow_theme`）→校验"开始探索"（模板 `bf/start_explore`）
  - 模板文件暂以占位（Slice 3 补真实素材）：`find` 失败时 logger.warning + 按坐标 fallback（若有已知坐标）或报错
  - 大型任务循环条件行改为 `if (conf.RG or conf.SSS or conf.RCL or conf.BF) and not rg_sleep:`
  - `LongTasks.vue` 的 `maa_long_task_options` 加 `{ label: '黑流树海刷钱 (Maa)', value: 'bf' }`（不需要额外配置项）
- Verification: 单元测试通过 + `ruff check`/`ruff format` 通过 + `npm run build` 通过（前端改动）
- Review: required
- Review reason: 调度循环核心改动 + 新导航函数，需确认分支结构与现有逻辑一致

## Slice 3: 导航模板入库 + 手机端验证

- Status: pending
- Kind: vertical
- Goal: 用用户提供的主力手机游戏截图制作导航模板（集成战略入口/黑流树海主题/开始探索界面），替换占位，并上机验证全链路
- Blocked by: Slice 2
- Scope: `arknights_mower/resources/`（新增 `bf/` 模板 png）、`arknights_mower/utils/recognize.py`（若需场景识别接线）、手机端部署验证（phone/dev）
- Matrix rows: Real entrypoint or integration path
- Public behavior: 导航模板齐全后，mower 能可靠识别黑流树海主题入口与"开始探索"界面，完成全自动导航
- Tests:
  - 本地：用用户截图裁剪的模板在对应分辨率截图上验证 `find` 命中（阈值 ≥0.5）
  - 上机（E2E）：手机端跑 `bf` 大型任务全链路
- Implementation notes:
  - 用户提供截图：长期探索页（含集成战略入口）、集成战略主题选择页（含黑流树海）、黑流树海主题页（含开始探索按钮）
  - 裁剪模板参照现有 `terminal_longterm_reclamation_algorithm.png`（526×150 风格，按钮级裁剪）
  - 跨分辨率：ORB 匹配有 0.8~1.25 缩放窗口，主力手机与挂机设备分辨率接近即可；不接近时需按挂机设备分辨率重新裁剪
- Verification: 本地模板命中验证 + E2E 上机通过
- Review: self-check
- Review reason: 模板素材类变更，无逻辑风险
- Stop conditions: 等待用户提供截图（手机在家）；上机验证需用户在家操作

## E2E Cross-Reference

- E1 手机端 MAA 能力验证：Slice 3 前置（user-run）
- E2 手机端 mower 上机验证：Slice 3（user-run）
