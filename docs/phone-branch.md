# 手机分支 `phone/dev`

> 命名说明：本想用 `dev/my-phone`，但 origin 已有分支 `dev`，Git 不能同时存在 `refs/heads/dev` 与 `refs/heads/dev/my-phone`，故使用 **`phone/dev`**。

本 fork 上的**长期手机集成分支**。只推 `origin`（WufeiHalf），**不**向 `upstream` 提 PR。

## 分支角色

| 分支 | 用途 |
| ------ | ------ |
| `upstream/dev` | 上游开发基线；feature 从这里开 |
| `feat/*` / `fix/*` | 单功能开发；PR 目标 = `upstream/dev` |
| **`phone/dev`** | 手机可运行全集：上游能力 + **手机环境补丁** + 当前在测 feature |

手机环境补丁（仅本分支长期保留，默认不进上游 PR）：

- `/start` 启动互斥锁（防多 worker）
- `/status` 在 `op_data` 未就绪时不崩
- MAA `asst` 优先 `maa_path/Python`，避免 site-packages 旧 shim

## 推荐工作流

```text
1. 开发
   git fetch upstream
   git checkout -b feat/<slug> upstream/dev
   # 改代码、单测、commit（Conventional Commits）

2. 上机验证（合进手机分支，不直接推 feature 文件盖手机）
   git checkout phone/dev
   git merge feat/<slug>          # 或 cherry-pick
   # 本机打包/推手机（见 my-mower-phone 脚本）
   # 真机验证

3. 验证通过 → 上游 PR（从 feature 分支，不是 my-phone）
   git checkout feat/<slug>
   git push -u origin feat/<slug>
   gh pr create --base dev --repo ArkMowers/arknights-mower

4. 上游合并后，刷新手机分支
   git checkout phone/dev
   git fetch upstream
   git merge upstream/dev         # 带走上游已合入的 feat，保留手机-only 提交
```

## 规则

1. **禁止** 对 `upstream` 开 `phone/dev` 的 PR。  
2. **禁止** 从随意 `feat/*` 单文件覆盖手机关键路径而不经 `phone/dev`（会冲掉环境补丁）。  
3. 手机-only 修复直接 commit 在 `phone/dev`，subject 建议带 `(phone)`。  
4. Feature PR 的 diff 应基于 `upstream/dev`，不要夹带手机-only 提交。  
5. `my-mower-phone/mower/` 是手机树镜像/运维侧快照；**代码真相源是本仓 `phone/dev`**。

## 与 my-mower-phone 的关系

| 仓 | 职责 |
|----|------|
| `arknights-mower` @ `phone/dev` | 手机可运行代码的 git 真相源 |
| `my-mower-phone` | ADB 脚本、文档、部署；`mower/` 可与 `phone/dev` 同步 |

上机推荐：在 `phone/dev` 检出后，用 my-mower-phone 的打包/推送脚本部署到 `/root/arknights-mower`。
