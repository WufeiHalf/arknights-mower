# Context

## Language

**MaaPart**:
The pydantic config block (`utils/config/conf.py`) holding MAA integration
fields: `maa_path`, `maa_conn_preset`, `maa_touch_option`, `maa_startup_check`.
The WebUI `MaaBasic.vue` component binds to these.
_Avoid_: "maa config" (ambiguous - could mean conf.yml MaaPart or MAA's own config.json).

**maa_path**:
Filesystem path to the user's MAA install dir (contains `MaaCore.dll`,
`resource/`, and the `Python/` folder mower imports `asst` from). Stored in
`config.conf.maa_path`. This is the path passed to `Asst.load()` and
`Updater(path, ...)`.
_Avoid_: "maa目录" in code comments is fine; in specs use `maa_path`.

**MaaCore**:
The native library MAA ships: `MaaCore.dll` (win) / `libMaaCore.so` (linux) /
`libMaaCore.dylib` (mac), loaded by mower via the Python ctypes binding
`asst.asst.Asst` (from `<maa_path>/Python/asst/`). mower never uses a CLI -
there is no released `MaaCLI` binary (the `src/Cpp/main.cpp` is a debug/smoke
test only). So "更新MAA/软件更新" = update MaaCore + resource + Python binding,
which is exactly what the MirrorChyan `rid=MAA` package contains.
_Avoid_: "MaaCLI", "maa cli" (no such released artifact).

**Updater**:
MAA's own Python update class at `asst/updater.py`. `Updater(path, version).update()`
performs a **full-package** update: downloads the whole release archive for the
host platform/arch and extracts it over `maa_path`, overwriting core + resources
together. Has no resource-only path and no rollback. This is the GUI's "Maa API"
fallback path (not MirrorChyan).
_Avoid_: "MAA updater" when meaning mower's wrapper around it.

**Version channel**:
The release channel selector: `stable` | `beta` | `alpha` (GUI names them
Stable/Beta/Nightly). Selects which version `api.maa.plus/.../version/summary.json`
or MirrorChyan returns. mower default: `stable`. User-selectable.
_Avoid_: "update type", "release track".

**tasks.json OTA**:
mower's own (non-MirrorChyan) auto-refresh of
`api.maa.plus/.../resource/tasks.json` into `<maa_path>/cache/resource/tasks.json`,
run in `BaseSchedulerSolver.initialize_maa()` on every base entry. Distinct from
the MirrorChyan resource update.
_Avoid_: conflating with "资源更新" (which syncs the whole `resource/` folder
via MirrorChyan).

**MirrorChyan**:
The paid CDN update service (`mirrorchyan.com`) the MAA GUI uses for BOTH
software and resource updates. Check API
`GET /api/resources/{rid}/latest?current_version=&cdk=&user_agent=` is free and
returns version info without a CDK; the download `url` is only returned when a
valid CDK is supplied. Without CDK, fall back to GitHub.
_Avoid_: "MAA官网", "api.maa.plus" (that's the old Python Updater path).

**CDK**:
MirrorChyan activation key (paid, per-user, from mirrorchyan.com). Required for
downloads; not required for version checks. In mower: stored as a plain config
field `mirrorchyan_cdk` (option A) shown in MaaBasic.vue only when update source
= MirrorChyan. The GUI stores it DPAPI-encrypted in `gui.json`; mower does NOT
read the GUI's store - user pastes the CDK into mower once.
_Avoid_: "token" (conflicts with webview.token), "key".

**rid**:
MirrorChyan resource identifier. `MaaResource` = the `resource/` folder sync
(version = `resource/version.json`'s `last_updated` timestamp, platform-
independent, incremental delta via changes.json). `MAA` = the software/core
package (platform-specific: needs `os`+`arch`+`channel` params; version =
`Asst().get_version()` from MaaCore; full-package, no incremental). mower derives
`os` from `__system__` (win/linux/macos) and `arch` from `platform.machine()`
(x64/arm64) - NOT hardcoded `os=win` like the GUI.

**phone/dev**:
The long-lived phone integration branch on `origin` (WufeiHalf fork). Contains
`upstream/dev` + phone-only environment patches + features under real-device
test. Never PRs to upstream. Deploy to phone via full-tree packaging, never
single-file overwrite. See ADR 0001.
_Avoid_: "dev/my-phone" (ref namespace conflict with existing `dev` branch).

**MasterySync**:
The scheduler component (`utils/mastery_sync.py`) that runs in `infra_main`'s
`todo_task` stage. Refreshes Skland data, syncs `cultivate.json` to DB, and
schedules pending mastery plans by enqueuing a shift-on task + SKILL_UPGRADE
task. Not the same as `plan_solver` (which must NOT add bare SKILL_UPGRADE).
_Avoid_: "专精调度" when meaning `plan_solver` (the old buggy path).

**mastery_plan state machine**:
DB states for a `(char_id, skill_index)` pair: `pending` -> `in_progress`
(with `expires_at`) -> `completed` | `failed`. Each state change inserts a new
row (append-only). `pending` = awaiting scheduling. `in_progress` = training
scheduled or running. `expires_at` is NULL until `skill_upgrade` confirm sets
it. See `.rope/specs/mastery/application-flow.md`.
_Avoid_: reusing a row's status field (always insert new).
