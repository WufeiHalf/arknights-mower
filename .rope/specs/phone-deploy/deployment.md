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
- Since 4.1.6-alpha.5 (2026-09), upstream's active line is **`upstream/alpha`
  (release tags `v4.1.6-alpha.N`)**, not `upstream/dev` (stale, pre-mastery
  refactor). Sync phone/dev by merging the alpha tag. After alpha.6, mastery
  code is fully upstream -- phone/dev carries no local mastery diffs. The
  complete local-diff list vs the alpha baseline lives in the meta repo:
  `my-mower-phone/docs/alpha-local-patches.md` (DroidCast fixes, asst path
  priority, fix-plan guard, maa_check, nav_trie steps; plus test-env gotchas
  -- run pytest with a clean `MOWER_DATA_DIR`, else the dev conf.yml flips
  performance_mode to "custom" and ~27 selection-timing tests fail).
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

**--clean trap (fixed in my-mower-phone 6c36c96)**: extraction must target
`-C $PROOT_MOWER --strip-components=1`. An earlier version extracted to
`-C /root`, dumping the whole tree flat into `/root` (server.py,
arknights_mower/, ...) while `/root/arknights-mower` stayed an empty shell;
python then imported the flat copy via sys.path fallback and WebUI came up
200 while `/start` failed on templates. Recovery: delete the flat files by
tar top-level manifest, redeploy.

## Phone Environment

- **Termux** + proot-distro ubuntu
- MAA at `/root/maa` (has `libMaaCore.so`, `Python/asst/`)
- ADB to phone: USB, or Tailscale `100.98.152.81:5555` (host `redmi-k30-5g`, sshd :8022; adbd tcp mode survives until phone reboot). All deploy scripts work identically over either -- `adb connect` first. Tailscale verified 2026-09-13 with full mower + MAA v6.17.5 deployment.
- touch: `maatouch`
- WebUI: `http://127.0.0.1:58000?token=mower` (adb forward), or directly `http://100.98.152.81:58000?token=mower` inside the tailnet
- Scripts: `restart-mower.sh`, `sync-to-phone.sh`, `push-dist.sh`,
  `package-and-push.sh` (in `my-mower-phone/scripts/`)
- Logs: `~/mower-service.log` (Termux home)
- `@internal` path contract (source-tree deploy has no `.git`):
  `find_git_root(cwd)` falls back to **cwd**, so mower must be started with
  cwd = `/root/arknights-mower` (mower.sh does `cd` there). If the tree is
  extracted anywhere else, jinja2 templates (`arknights_mower/templates/`)
  are not found and `/start` dies with TemplateNotFound.

## Dependency Changes (offline install)

Upstream 4.1.5.8 (#904) swapped pandas->stdlib csv, jieba->rjieba. Phone
container has no reliable pip network; install wheels offline:

```bash
# laptop (proxy): download aarch64 wheel
pip download rjieba==0.2.1 --platform manylinux2014_aarch64 \
  --only-binary=:all: --python-version 3.12 --no-deps -d /tmp/rjieba-pkg
# keep the canonical wheel FILENAME (pip rejects rjieba.whl)
adb push /tmp/rjieba-pkg/<full-wheel-name> /data/local/tmp/
# then into container: pip install --break-system-packages <wheel>
```

Old pandas/jieba stay installed (unused, harmless) -- do not uninstall
(numpy is shared with other local scripts).

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
+ `npm run build` (in `ui/`) before pushing phone/dev. The vite build step
catches unresolved merge-conflict markers inside JSON/vue assets that
`git add -A` happily commits (hit 2026-09-13: event_data.json shipped with
conflict markers, only surfaced at build; fixed in ee67eab07).

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
