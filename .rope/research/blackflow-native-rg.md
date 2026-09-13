# 黑流树海原生 RG 通道（上游支持现状）

## Question

放弃本地牛杂方案后，黑流树海刷钱由 MAA 原生 Roguelike 主题承接——
上游 mower 支持现状如何、手机环境是否就绪、Roguelike 参数对 BlackFlow
主题的适用性如何？

## Verified Facts

### 上游 alpha 已含完整支持

Fact: `upstream/alpha`（4.1.6-alpha.4+，tip 2026-09-13 = 683d3ecce）已合并
全部黑流树海 RG 支持：
- #991（3fd6822fb，2026-09-08）：肉鸽通用字段按主题/策略条件下发——
  后端 `investment_with_more_score` 排除 BlackFlow、`refresh_trader_with_dice`
  仅 Mizuki、坍缩范式仅 Sami+策略5、黑流树海字段（`blackflow_cultivation_target`，
  swaddled_cat/feathered_serpent/dog/cerberus）仅刷襁褓动物模式；前端
  MaaRogue.vue 含黑流树海主题选项、专属分队列表、职业组（灵活部署/坚不可摧）、
  推荐配置文案
- #994（03036988b）：玩法字段补齐 + 企鹅物流上报 id
- #1009（38c11300b，2026-09-09）：黑流树海启动前场景超时误退出修复
  （`recog.reset_after_external_control()`）+ 任务结束后 SwitchTheme 恢复主题
  （需 MAA ≥ 6.17.3，新 conf 字段 maa_restore_theme_enable/maa_restore_theme）
Source: git show upstream/alpha（3fd6822fb / 03036988b / 38c11300b）
Verified by: 本地 git（2026-09-13 fetch upstream）
Stability: high（已合并提交，只在 alpha 分支）
Implication: 无需自研对接；等 alpha→dev 合并后同步 phone/dev 即可。同步时
注意 phone/dev 本地在 base_schedule.py（22 hunks）与 MaaBasic.vue（176 行
MAA 更新 UI）有改动，解冲突是主要工作量；alpha 的专精修复（#1036~#1054）
与本地平行修复重叠，合并后可停掉本地维护。

### upstream/dev 停滞

Fact: upstream/dev tip = 562168aad（2026-08-14，4.1.5.8），落后 alpha 158
commits；phone/dev 已含 dev tip。alpha→dev 合并时点未知。
Source: git log upstream/dev / upstream/alpha
Verified by: 本地 git
Stability: low（随上游发布节奏变化）
Implication: 黑流树海上机验证推迟到 alpha→dev 同步后的独立 issue（用户
决策 2026-09-13：等合并，不 cherry-pick、不直接合 alpha）。

### 手机环境就绪

Fact: 手机 MAA = v6.17.5（libMaaCore.so strings），`resource/roguelike/BlackFlow/`
齐全（strategy.json、recruitment.json、shopping.json、node_execution.json 等），
资源最后更新 2026-09-11。满足原生 RG 主题要求，无需升级。
Source: ssh root@100.98.152.81 -p8022 → proot-distro login ubuntu → /root/maa
Verified by: strings + resource/version.json
Stability: medium（OTA 更新只增版本）
Implication: 上游同步后直接可用。若手机 conf.yml 残留
`maa_long_task_type: "bf"`，下次部署时手动改为 "rogue" 并在 UI 选主题
黑流树海（不进代码，回退后 LongTasks 无 bf 选项）。

## Assumptions

- 无

## Open Questions

- alpha→dev 合并时点（上游节奏，不可控；同步 issue 启动前重新 fetch 确认）
