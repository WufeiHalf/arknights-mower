# 集成战略：黑流树海刷钱（牛杂） E2E

## E1 手机端 MAA 能力验证

Executor: user
Risk: remote-readonly（手机端 MAA GUI 查看/试跑，无 mower 写操作）
Gate Decision: user-run
Approved Action: 用户在手机端确认 MAA 版本与牛杂刷钱入口可用性
Scope: 手机端 MAA GUI（非 mower 代码、非挂机手机配置）
Command or Steps:
- 手机端打开 MAA GUI，确认版本 ≥ v6.14.0（设置-关于 或版本号显示）
- 在 MAA 的牛杂（MiniGame/小游戏）模块查看是否有"黑流树海刷钱"入口
- 如有，手动跑一轮确认任务链可用（进入游戏黑流树海"开始探索"界面后启动）
Pass Criteria:
- MAA 版本号 ≥ v6.14.0
- 牛杂模块可见"黑流树海刷钱"入口（即资源已更新到含 BlackFlowTemporary）
- 手动跑通至少一轮（或能明确识别入口且任务链开始执行）
Failure Report:
- 手机端 MAA 版本号
- 牛杂入口是否可见（截图或文字描述）
- 若报错：报错文案、卡在哪个步骤
Forbidden Out-of-Scope Actions:
- 不在手机上执行任何 mower 部署、文件覆盖或服务重启
- 不修改手机端 MAA 配置（更新资源属于 MAA GUI 正常操作，可执行）
Result:
- pending

## E2 手机端 mower 上机验证

Executor: user
Risk: remote-write（phone/dev 部署 + 真实游戏操作）
Gate Decision: user-run
Approved Action: 用户在家时把功能合入 phone/dev 部署到手机，跑一次 `bf` 大型任务全链路
Scope: phone/dev 分支部署的手机环境（/root/arknights-mower）
Command or Steps:
- 将功能（conf.BF + 预检 + to_blackflow + 模板）合入 phone/dev，`package-and-push.sh` 部署
- 手机端 conf.yml 设置 `maa_rg_enable: 1`、`maa_long_task_type: "bf"`
- 在时间窗内观察 mower 日志：预检通过 → 自动导航 → append Custom 任务 → MAA 刷钱启动
Pass Criteria:
- 预检通过（MAA 版本 + BlackFlowTemporary 存在性）
- mower 自动导航到黑流树海"开始探索"界面（无需手动干预）
- MAA 日志出现 BlackFlowTemporary 任务链执行（投资/行动力/重开相关输出）
- 到达任务时间点或 stop_maa 后正常停止，无崩溃
Failure Report:
- mower 日志文件（导航卡在哪、报错内容）
- 卡住时的游戏截图
- 预检报错文案（若有）
Forbidden Out-of-Scope Actions:
- 不在验证中改动其他大型任务配置（RG/SSS/RCL 保持原样）
- 不跑与本次无关的部署操作
Result:
- pending
