# Phone Deployment via phone/dev + package-and-push

## Scope

When deploying mower code to the Android phone (proot ubuntu on Termux),
use the `phone/dev` branch as the single source of truth and
`package-and-push.sh` for full-tree deployment. Do NOT push individual
files from arbitrary feature branches -- that overwrites phone-only
patches.

## Branch Model

```
upstream/dev  ──>  feat/* (开发 + PR)
                        │
                        │ merge
                        ▼
                     phone/dev (手机可运行全集，只推 origin)
                        │
                        │ package-and-push.sh
                        ▼
                   手机 /root/arknights-mower
```

- `phone/dev` lives on `origin` (WufeiHalf fork) only. Never open a PR
  to `upstream` from it.
- Feature branches always branch from `upstream/dev`, not `phone/dev`.
- Before deploying to phone, merge the feature branch into `phone/dev`.
- After upstream merges the feature, `phone/dev` does `git merge upstream/dev`
  to absorb it, keeping phone-only patches.

## Naming

Cannot use `dev/my-phone` because `origin` already has a branch named
`dev`. Git cannot have both `refs/heads/dev` and `refs/heads/dev/my-phone`
(ref namespace conflict). Use `phone/dev` instead.

## Deployment Script

`my-mower-phone/scripts/package-and-push.sh`:

```bash
# 普通覆盖（日常）
./scripts/package-and-push.sh

# 净重置（上游删文件时，自动备份恢复用户数据）
./scripts/package-and-push.sh --clean

# 只部署不重启
./scripts/package-and-push.sh --no-restart
```

Flow: `git archive phone/dev` → `npm run build` (ui/dist) →
tar.gz (excluding user data) → `adb push` → proot extract → restart.

## User Data Preservation

The tar **excludes** these files/dirs so phone user data is never touched:

- `conf.yml` / `plan.json` / `state.json` (git-untracked anyway)
- `weekly_plans.json` / `weekly_plans.yml`
- `tmp/` (contains `data.db`, `cultivate.json`, `report.csv`, etc.)

Verified by md5 comparison: git repo has no `conf.yml` at all
(`.gitignore` excludes `*.yaml`), so it can never be in the tar.

`--clean` mode backs up these files to `/root/.mower-backup/` before
deleting the tree, then restores them after extraction.

## Phone Environment

- **Termux** + proot-distro ubuntu
- MAA at `/root/maa` (has `libMaaCore.so`, `Python/asst/`)
- ADB: `127.0.0.1:5555`, touch: `maatouch`
- WebUI: `http://127.0.0.1:58000?token=mower`
- Scripts: `restart-mower.sh`, `sync-to-phone.sh`, `push-dist.sh`,
  `package-and-push.sh` (in `my-mower-phone/scripts/`)
- Logs: `~/mower-service.log` (Termux home)

## Phone-Only Patches (on phone/dev, not in upstream PRs)

These patches live on `phone/dev` long-term:

1. `mower_thread_lock` in `server.py` `/start` (prevent multi-worker)
2. MAA `asst` path priority: `sys.path.insert(0, maa_path/Python)` +
   purge stale `asst` modules (in both `base_schedule.initialize_maa`
   and `maa_check.py`) -- site-packages may have an old `asst` shim
   that loads but `connect()` fails. See `asst-path-priority.md`.
3. `/status` hardening when `op_data` not ready
4. **MAA 软件/资源更新功能** (`utils/maa_update.py`, 5 commits on
   `phone/dev`, upstream/dev has NO `maa_update.py`): conf fields
   `maa_update_source/channel/mirrorchyan_cdk/proxy`, async version
   check (`schedule_async_check` in `initialize_maa`), pending download
   + apply on startup (`__main__.main`), `server.py` `maa_update_job`,
   `MaaBasic.vue` update UI. Not yet PR'd upstream.

### 合入上游 #901/#895 时的共存事实 (merge `1389754f6`)

When upstream refactors the same files, keep BOTH sides - the patches
are complementary, not conflicting. Resolved in `1389754f6`:

- `__main__.py`: phone's `apply_pending_software` block + upstream's
  `is_maa_connectivity_check_enabled` flow (drop the old
  `startup_maa_check = should_check_maa_before_start()` line - the
  function no longer exists after #901)
- `conf.py`: phone `maa_update_*` fields + upstream docstring for
  `maa_startup_check`
- `base_schedule.py`: phone `schedule_async_check` + upstream
  `check_maa_connectivity` / `rest_after_maa` methods
- `server.py`: import `Lock, RLock, Thread` (phone Lock + upstream RLock);
  keep both `maa_update_job` (phone) and `maa_check_lock` (upstream)
- `mastery_recommendation.py`: `planned_skills` param first, else DB
  `get_all_plans()` (upstream #895 removed the matery_plan.json file)
- `mastery_sync.py`: upstream expired-`in_progress` recovery + phone
  Skland-guard / `_auto_complete_level3`

After merging, always: `unittest discover -p "*_tests.py"` + `ruff`
before pushing phone/dev.

## Wrong vs Correct

### Wrong

```bash
# 从任意 feat 分支单文件覆盖手机
cp fork/server.py phone-mirror/mower/server.py
adb push ... server.py  # 覆盖了手机里的 mower_thread_lock
```

### Correct

```bash
# merge 到 phone/dev 再全量部署
git checkout phone/dev && git merge feat/foo
./scripts/package-and-push.sh
```
