# MAA Update API (MirrorChyan + Python Updater)

## Question

How does the MAA GUI implement "软件更新" (software) and "资源更新" (resource)
updates, and what API can mower call to mirror those two buttons? Can mower
"等价于点击 MAA GUI 的更新按钮" by reusing the user's existing GUI CDK?

## Verified Facts

### mirrorchyan-is-the-distribution-service

Fact: The MAA GUI (WPF, `VersionUpdateSettingsUserControlModel.cs` on `dev-v2`)
updates **both** software and resources through **MirrorChyan**
(`mirrorchyan.com`), a paid CDN update service. The settings model has a
`MirrorChyanCdk` property (user-entered activation key). On startup the GUI
calls `VersionUpdateDialogViewModel.ShowUpdateOrDownload()` which runs
`VersionUpdateAndAskToRestartAsync()` (software) +
`ResourceUpdater.ResourceUpdateAndReloadAsync()` (resource). So "走maa的逻辑" =
call the MirrorChyan API the same way the GUI does.
Source: dev-v2 `VersionUpdateSettingsUserControlModel.cs` + `RootViewModel.cs:38-82`
Verified by: raw source read
Stability: high
Implication: Both buttons route through MirrorChyan. The user must supply a CDK
for downloads (see cdk-stored-dpapi-encrypted-in-gui-json).

### check-api-is-free-no-cdk

Fact: The check endpoint needs no CDK:
`GET https://mirrorchyan.com/api/resources/{rid}/latest?current_version=<local>&user_agent=<ua>`
Returns `{code, msg, data:{version_name, version_number, channel, os, arch,
release_note, url?, cdk_expired_time?}}`. The `url` field is present ONLY when
there is a newer version AND a valid CDK is supplied. Without CDK, check still
returns `version_name`/`version_number` so the client can compare and show
"有更新"; it just gets no download URL. MirrorChyan docs explicitly say:
"推荐即使未填写 CDK 时也使用 Mirror酱 API 检查".
Source: <https://github.com/MirrorChyan/docs> (README.md), live probe of mirrorchyan.com
Verified by: `curl https://mirrorchyan.com/api/resources/MaaResource/latest` -> code 0 with version_name=2026-07-10 16:30:29.000, version_number=259, no url field
Stability: high
Implication: The async "检查更新" the user wants is FREE and needs no CDK.
Showing purple "软件/资源有更新" works without any paid key. Only the actual
download needs the CDK (or GitHub fallback).

### cdk-error-codes

Fact: CDK download error codes: 7001 KEY_EXPIRED, 7002 KEY_INVALID, 7003
RESOURCE_QUOTA_EXHAUSTED (daily cap), 7004 KEY_MISMATCHED (CDK type doesn't
match resource), 7005 KEY_BLOCKED. Code 8001 RESOURCE_NOT_FOUND = wrong
rid/channel/os/arch. Code 0 = success.
Source: <https://github.com/MirrorChyan/docs/blob/main/ErrorCode.md>
Verified by: doc read
Stability: high
Implication: mower must surface these clearly (esp. quota exhausted, key expired).

### cdk-stored-dpapi-encrypted-in-gui-json

Fact: The GUI stores `MirrorChyanCdk` in `<maa_path>/config/gui.json` under key
`VersionUpdate.ResourceUpdateSource.MirrorChyanCdk`, **encrypted with Windows
DPAPI** (`ProtectedData.Protect`, `CurrentUser` scope, via
`SimpleEncryptionHelper`). DPAPI-CurrentUser means: only the same Windows user
account on the same machine can decrypt it; the key is derived from the user's
login credentials, not a hardcoded secret. So mower (running as the same Windows
user) could in principle read gui.json and DPAPI-decrypt the CDK - but only via
a Windows-native call (PowerShell
`[System.Security.Cryptography.ProtectedData]::Unprotect` or a tiny C#/dotnet
helper), NOT from pure cross-platform Python. On non-Windows, gui.json's CDK is
unusable from mower anyway (DPAPI is Windows-only). The CDK is otherwise just a
string passed as a query param to MirrorChyan - mower can also simply ask the
user to paste it into a mower config field.
Source: dev-v2 Helper/SimpleEncryptionHelper.cs:22-93, Helper/ConfigurationHelper.cs:28, Constants/ConfigurationKeys.cs:236
Verified by: full source read of SimpleEncryptionHelper (ProtectedData.Protect/Unprotect, DataProtectionScope.CurrentUser)
Stability: high
Implication: "Read the CDK the user already typed into the MAA GUI" is possible
on Windows (same user) but requires a DPAPI unprotect step - Python alone can't
do it without a native helper. This is the crux of the user's
"等价于点GUI更新" question.

### gui-has-no-cli-trigger-for-update

Fact: The MAA GUI (`MaaWpfGui.exe`) accepts only `--config` as a CLI argument
(Bootstrapper.cs:643 `ConfigFlag = "--config"`). There is **no** command-line
flag, no IPC pipe, no exposed API, and no headless entry point to trigger
"software update" or "resource update" from outside. The update is driven
entirely by `VersionUpdateDialogViewModel.ShowUpdateOrDownload()` called from
`RootViewModel.OnViewLoaded()` (on GUI window load). The only externally-runnable
artifact is the shipped `MAA.Updater.exe` (a self-contained updater binary
included in update packages, referenced by `PendingUpdateApplier`), but it
applies an already-downloaded pending package - it does not itself check
MirrorChyan or fetch by rid. So there is no way to say
"launch MaaWpfGui.exe with --update-software" and have it do the GUI's update
flow headlessly.
Source: dev-v2 Bootstrapper.cs:643-664 (ParseArgs), RootViewModel.cs:38-82 (OnViewLoaded -> ShowUpdateOrDownload), PendingUpdateApplier.cs (applies pre-existing package only)
Verified by: source read of Bootstrapper arg parsing + RootViewModel startup flow + PendingUpdateApplier
Stability: high
Implication: "等价于点击MAA GUI的更新按钮" is NOT achievable by launching the
GUI with a flag. The only way to get GUI-equivalent behavior is to
**reimplement the MirrorChyan API calls** in mower (Python), reproducing the
exact URLs/params the GUI uses (now fully documented below). The CDK still has
to come from somewhere - see cdk-stored-dpapi-encrypted-in-gui-json.

### resource-check-exact-url-and-params

Fact: The GUI's exact resource check URL (from
`ResourceUpdater.CheckFromMirrorChyanAsync`, dev-v2
Models/ResourceUpdater.cs:126):
`GET https://mirrorchyan.com/api/resources/MaaResource/latest?current_version=<urlencoded timestamp>&cdk=<cdk>&user_agent=MaaWpfGui&sp_id=<machineguid_hash>`

- `current_version` = the local resource version timestamp, read from
  `<maa_path>/resource/version.json` `last_updated` (e.g.
  "2026-07-10 16:30:29.000"), formatted `yyyy-MM-dd+HH:mm:ss.fff` (e.g.
  `2026-07-10+16:30:29.000`).
- Same `cdk`, same `sp_id`, same `user_agent` as the software path.
- Response: `data.version_name` (remote timestamp), `data.version_number` (int),
  `data.url` (incremental delta download URL) present only when newer + valid
  CDK; `data.cdk_expired_time`.
- If `code != 0`: handles KEY_EXPIRED/INVALID/etc (7001-7005) like software.
- The resource download is an **incremental** delta zip with `changes.json`
  (added/modified/deleted/added_dir/deleted_dir).
- CDK-free fallback exists: `UpdateFromGithubAsync()` downloads
  `https://github.com/MaaAssistantArknights/MaaResource/archive/refs/heads/main.zip`
  (full resource folder, no version compare) and merges `resource/` over BaseDir.
Source: dev-v2 Models/ResourceUpdater.cs:126-210 (full method read), MaaUrls.cs:85/91
Verified by: full source read of `CheckFromMirrorChyanAsync` + `UpdateFromGithubAsync` + `MaaUrls`
Stability: high
Implication: Resource check is also a single GET, simpler than software (no
os/arch/channel). mower can replicate exactly. The `current_version` timestamp
format and the `version.json` path under `maa_path/resource/` are the only
mower-side inputs.

### software-check-exact-url-and-params

Fact: The GUI's exact software check URL (from
`VersionUpdateDialogViewModel.CheckUpdateByMirrorChyan`, dev-v2:958):
`GET https://mirrorchyan.com/api/resources/MAA/latest?current_version=<core_version>&cdk=<cdk>&user_agent=MaaWpfGui&os=win&arch=<x64|arm64>&channel=<stable|beta|alpha>&sp_id=<machineguid_hash>`

- `current_version` = `Asst().get_version()` (e.g. "v6.14.1"), captured as
  `_curVersion`.
- `arch` = `IsArm ? "arm64" : "x64"`.
- `channel` = `VersionType` enum -> `stable|beta|alpha` (Nightly=alpha,
  Beta=beta, else stable).
- `sp_id` = `HardwareInfoUtility.GetMachineGuid().StableHash()` (a stable
  per-machine id; mower can substitute its own stable id or omit).
- Response carries `data.cdk_expired_time` (long, seconds) and `data.url`
  (download URL) ONLY when `cdk` is non-empty AND a newer version exists. If
  `cdk` empty -> returns `CheckUpdateRetT.NoMirrorChyanCdk` ("有新版本但未填写
  cdk").
- Downloaded file is `MirrorChyanApp<version_name>.zip`, full-package (no
  incremental delta for software in this path), requires
  `_requiresFullPackageConfirmation` user confirm before download.
Source: dev-v2 VersionUpdateDialogViewModel.cs:958-1015 (full method read), MaaUrls.cs:90 (`MirrorChyanAppUpdate`)
Verified by: full source read of `CheckUpdateByMirrorChyan` + `MaaUrls`
Stability: high
Implication: The software check is a single GET with all params inline. mower
can replicate it exactly. NOTE: mower loads MaaCore.dll in-process during tasks,
so `get_version()` must run in a child process like `maa_check.py` does (DLL
already loaded locks the file).

### incremental-format

Fact: MirrorChyan delta packages include a `changes.json` describing the diff
between two versions: fields `added`, `modified`, `deleted` (file lists),
`added_dir`, `deleted_dir` (dir lists), paths `/`-separated relative to package
root. Absent fields = no changes in that category. Integration flow: extract
package -> if changes.json exists, delete `deleted` files/dirs -> overlay
`added`/`modified`. For the running program itself, rename-then-delete-on-next-
start is recommended (file may be locked).
Source: <https://github.com/MirrorChyan/docs/blob/main/Incremental.md>
Verified by: doc read
Stability: high
Implication: Resource update is incremental + safe (small delta). Software
update touches MaaCore.dll which may be locked if mower has loaded it -> need
pre-check that no MAA task is running / DLL not loaded in this process.

### python-updater-is-alternative-full-package

Fact: MAA also ships `asst/updater.py` (`Updater(path, Version).update()`)
which does a **full-package** software-only update via `api.maa.plus` version
API + GitHub release zip (~266MB win-x64), `extractall` over `maa_path`, no
rollback, no resource handling, no CDK needed. Shipped in the release zip's
`Python/` folder (mower already imports `asst.asst`/`asst.utils` from there).
Requires `requests` (mower pins 2.31.0). Uses `multiprocessing` to read
version in a child (avoids holding DLL in parent). This is the GUI's **Maa API**
fallback path (`CheckUpdateByMaaApi`), not the MirrorChyan path.
Source: src/Python/asst/updater.py (master + dev-v2), root CMakeLists.txt
Verified by: source read + CMake `install(DIRECTORY src/Python DESTINATION .)`
Stability: high
Implication: For software update, there are TWO viable paths: (A) MirrorChyan
(matches GUI default, but needs CDK), (B) Python `Updater` / Maa API (no CDK,
but 266MB full package, no incremental). Resource update has no Python-Updater
equivalent - only MirrorChyan (or the MaaResource repo zipball as CDK-free
fallback).

### mower-already-does-tasks-json-ota

Fact: mower already refreshes `api.maa.plus/.../resource/tasks.json` into
`<maa_path>/cache/resource/tasks.json` on every base entry in
`BaseSchedulerSolver.initialize_maa()` (~base_schedule.py:4060), loaded via
`Asst.load(path, incremental_path=path/'cache')`. This is mower's own code, NOT
the MirrorChyan resource update. The two are complementary: tasks.json =
activity stage nav overlay (already auto); MirrorChyan resource = full
resource/ folder sync (new).
Source: arknights_mower/solvers/base_schedule.py
Verified by: source read
Stability: high
Implication: The new "更新资源" button is distinct from the existing auto
tasks.json OTA. Don't conflate them.

### mower-maacheck-subprocess-pattern

Fact: mower runs MAA-touching logic in short-lived subprocesses already:
`utils/maa_check.py` builds a `python -c <script>` command + JSON params, runs
via `subprocess.Popen`/`subprocess.run`, parses stdout JSON for status. server.py
wraps this in a `maa_check_job` dict with id/process/status/message/started_at +
a `_collect_maa_check_result()` poller + `/check-maa` + `/check-maa/status`
routes. This is the established pattern for: don't load MaaCore.dll in the
long-lived server process, capture progress via stdout, expose start/status
endpoints to the Vue frontend (which polls status in a loop).
Source: arknights_mower/utils/maa_check.py, server.py /check-maa routes
Verified by: source read
Stability: high
Implication: The update buttons should reuse this exact pattern: a
`maa_update.py` script run as a subprocess, a `maa_update_job` state dict in
server.py, `/maa-update/<kind>` (start) + `/maa-update/status` (poll) routes,
Vue polls like `test_maa()` does. Mirror the existing UX.

## Assumptions

- The async update check ("每次拉起maa时") should run wherever mower initializes
  MAA - the most likely hook is `BaseSchedulerSolver.initialize_maa()` (already
  runs on every base entry) OR mower/server startup. Needs decision.
- mower runs on the same host as the MAA install it manages (maa_path is local).
- mower is cross-platform: `arknights_mower/__init__.py` defines
  `__system__ = platform.system().lower()` ("windows"/"linux"/"darwin"), and
  server.py uses it for `CREATE_NO_WINDOW` gating. So the update logic must
  detect the HOST os (where mower runs = where MaaCore lives) and pass the
  matching `os`/`arch` to MirrorChyan. This is a DEVIATION from the MAA GUI,
  which hardcodes `os=win` because the WPF GUI is Windows-only.

## Verified Facts (addendum)

### mower-uses-maacore-via-python-ctypes-not-cli

Fact: mower loads MaaCore **directly through the Python ctypes binding**
(`asst.asst.Asst`), NOT via any CLI binary. In
`BaseSchedulerSolver.initialize_maa()` (base_schedule.py ~4039-4045):
`asst_path = os.path.dirname(path / "Python" / "asst")`; appended to `sys.path`;
`from asst.asst import Asst`; `Asst.load(path=path, incremental_path=path/
"cache")`. The `asst.asst.Asst.load()` (verified earlier in asst.py) opens
`MaaCore.dll` (win) / `libMaaCore.dylib` (mac) / `libMaaCore.so` (linux) via
ctypes and calls `AsstLoadResource`. A full-repo grep for `maacli`/`MaaCLI`/
`main.cpp` returns ZERO hits in mower. So mower never shells out to a MAA CLI.
Source: arknights_mower/solvers/base_schedule.py:4039-4045, arknights_mower/**init**.py:16
Verified by: source read + repo-wide grep (no CLI references)
Stability: high
Implication: "更新MAA" = update the MaaCore library + resource (+ the Python
binding folder), exactly what the MirrorChyan `rid=MAA` package contains. There
is no separate "MaaCLI" to install or read.

### maa-has-no-released-cli-only-package

Fact: MAA's `src/Cpp/main.cpp` is compiled only as `debug_demo`/`smoke_test`
executables (`src/Cpp/CMakeLists.txt: add_executable(debug_demo main.cpp)`),
both under `if(ASST_DEBUG)`-style gating; there is no released `MaaCLI`
binary. The release assets per platform are: win-x64 zip (full: WPF GUI +
MaaCore.dll + resource + Python), linux-x86_64/aarch64 `.AppImage` + `.tar.gz`
(MaaCore.so + resource + Python, no GUI), macos-universal `.dmg`/`.zip`.
All packages bundle the same `resource/` folder and the `Python/asst/` binding.
Source: dev-v2 src/Cpp/CMakeLists.txt, api.maa.plus stable.json assets list
Verified by: CMake read + asset enumeration
Stability: high
Implication: Whatever platform mower runs on, the user's `maa_path` is one of
these install types, and the MirrorChyan `rid=MAA` package for that `os`/`arch`
is the correct update target. mower must send `os` based on `__system__`
(`windows`->`win`, `linux`->`linux`, `darwin`->`macos`) and `arch` based on
`platform.machine()` (`x86_64`/`AMD64`->`x64`, `aarch64`/`arm64`->`arm64`).

### gui-hardcodes-os-win-mower-must-not

Fact: The MAA GUI's software-check URL hardcodes `os=win` and `arch` from
`IsArm` (VersionUpdateDialogViewModel.cs:967-973). The GUI is Windows-only so
this is fine for it. But mower runs on Windows/Linux/macOS, so mower MUST derive
`os`/`arch` from `platform.system()`/`platform.machine()` instead. The
MirrorChyan `rid=MAA` resource has per-os/arch variants (the no-CDK probe of
`rid=MAA` without os/arch/channel returned 8001 RESOURCE_NOT_FOUND - it needs
those params to resolve). `channel` is the user's chosen update channel
(default `stable`).
Source: VersionUpdateDialogViewModel.cs:967-973 (os=win hardcoded), live probe (8001 without params)
Verified by: source read + API probe
Stability: high
Implication: "和maa gui同等逻辑" must be interpreted as "same MirrorChyan
API and params" but with os/arch sourced from the host, NOT copied verbatim
from the GUI. This is the one place mower diverges from the GUI, necessarily.

## Verified Facts (phone/linux addendum, 2026-08-02 实测)

### linux-aarch64-package-layout-varies

Fact: MAA linux-aarch64 release tar.gz layout is NOT stable across versions:
older packages wrap contents in `MAA-vX.Y.Z-linux-aarch64/`, while
**v6.16.0 extracts flat** (AsstCaller.h, libMaaCore.so, Python/, resource/,
maa binary all at top level; ~9445 files, 199MB tar.gz). Any extract-and-
repackage tooling must detect "single top-level dir" vs "flat" instead of
assuming either. asset name pattern:
`^MAA-.*-linux-aarch64\.tar\.gz$` on api.maa.plus stable.json
`details.assets[].browser_download_url` (github release direct link,
199MB download verified through http proxy 127.0.0.1:8118).
Source: live download+extract of v6.16.0 (2026-08-02)
Stability: medium (layout may vary per version)
Implication: phone update script re-tars with flat root;
self-check must verify libMaaCore.so + Python/asst + resource/version.json.

### maaresource-zip-layout

Fact: MaaResource `main.zip` (13MB) extracts to
`MaaResource-main/{resource,cache,LICENSE,README.md,.github}`; the
`resource/` dir holds ~4951 files / ~105MB (Arknights-Tile-Pos alone has
thousands of json). `resource/version.json` is readable via
`raw.githubusercontent.com/MaaAssistantArknights/MaaResource/main/resource/version.json`
(last_updated timestamp) - usable for remote version compare without
cloning. Overlay semantics: NEVER replace the whole `resource/` with the
zip content (full release package's OCR/models would be lost) - copy over.
Source: live download+extract (2026-08-02)
Stability: high
Implication: resource update = overlay + refresh
`cache/resource/tasks.json` (api.maa.plus/.../resource/tasks.json, 16KB).

### asst-get-version-needs-load-and-instance

Fact: `Asst.get_version()` is an **instance method** and requires
`Asst.load(maa_path)` first (sets the `__lib` class attr); calling it
unbound or before load raises `TypeError: missing 1 required positional
argument: 'self'` / `AttributeError` on `__lib`. Verified on phone v6.14.1
and v6.16.0. On aarch64 phones: `PYTHONPATH=maa/Python LD_LIBRARY_PATH=maa`.
Source: phone asst.py:84/244, live probe (2026-08-02)
Stability: high
Implication: version probes must `Asst.load(path); Asst().get_version()`.

## Open Questions

- CDK source: DECIDED - option A (mower's own `mirrorchyan_cdk` config field +
  MaaBasic.vue input, shown only when update source = MirrorChyan).
- Update channel: DECIDED - default `stable`, user-selectable (stable/beta/alpha
  matching GUI's Nightly/Beta/Stable).
- Update source: DECIDED - user-selectable GitHub or MirrorChyan. When
  MirrorChyan selected, show CDK input.
- HTTP proxy: DECIDED - add a configurable http proxy field, applied to the
  update HTTP requests (MirrorChyan check/download + GitHub fallback), matching
  GUI's proxy behavior.
- Async check hook point and frequency: DECIDED - hook in
  `BaseSchedulerSolver.initialize_maa()`, throttled to 6h (hardcoded, not
  configurable), async `Thread(daemon=True)`, result in a global state dict
  surfaced via a new `/maa-update/check-status` route.
- UI for in-progress update: DECIDED - status text pattern like `test_maa()`
  (Vue polls `/maa-update/status` in a loop), not a progress bar. Button click
  re-checks fresh (ignores throttle), downloads+applies, and on "already latest"
  shows a frontend popup "已经是最新版本".
- Software update apply model: DECIDED - option B (download to
  `maa_path/.pending_update/`, apply at mower startup before `initialize_maa`,
  NOT hot-reload, NOT force-restart). Aligns with GUI's pending-package model.
  Resource update applies in-place + hot reloads `Asst.load()` (no restart).
- Platform routing: DECIDED - option A-1. Windows = both sources selectable;
  Linux = GitHub only (MirrorChyan greys out, 8001);
  macOS = MirrorChyan only (GitHub greys out, Updater has no darwin branch).
  macOS GitHub gap NOT backfilled (A-2 rejected).

## Verified Facts (cross-platform addendum)

### cross-platform-coverage-matrix

Fact: No single self-implemented update path covers all three platforms. Live
probes of MirrorChyan `rid=MAA` (no CDK, with os/arch/channel) and source reads
of `asst.updater.Updater` yield this coverage:

| Path | win | linux | macos |
| ------ | ----- | ------- | ------- |
| MirrorChyan rid=MAA (software) | OK (v6.14.1) | 8001 not found | OK (v6.14.1) |
| MirrorChyan rid=MaaResource (resource) | OK | OK (platform-independent) | OK |
| asst.updater.Updater (GitHub+api.maa.plus) | OK (win-x64/win-arm64) | OK (linux-x86_64/linux-aarch64) | BROKEN (no darwin branch, falls back to win-x64 -> no asset match) |

MirrorChyan `rid=MAA` returns 8001 RESOURCE_NOT_FOUND for linux/x64 and
linux/arm64 (probed 2026-07-12). The `asst.updater.Updater.get_download_url`
only branches on `platform.system() == "Linux"` or `"Windows"`; "Darwin" is
unhandled -> stays at default `win-x64` -> regex `^MAA-.*-win-x64\.(zip|tar.gz)$`
won't match the macOS asset `MAA-v6.14.1-macos-universal.zip`.
Source: live MirrorChyan probes (os=linux/* -> 8001), dev-v2 asst/updater.py:122-139 (platform detection), api.maa.plus stable.json asset names
Verified by: curl probes + source read
Stability: high
Implication: The user-chosen (A) scheme [MirrorChyan + GitHub fallback] has
TWO platform gaps: (1) Linux+MirrorChyan -> must fall back to GitHub (which
works via Updater); (2) macOS+GitHub-fallback -> Updater can't resolve the asset.
So macOS users MUST use MirrorChyan (which works), and Linux users MUST use
GitHub fallback (MirrorChyan unavailable). Windows works on both. The UI must
guide this (e.g. disable/grey the inapplicable source per platform, or auto-
fall back with a notice).

### maa-cli-is-cross-platform-updater-but-mower-does-not-use-it

Fact: MAA maintains a SEPARATE cross-platform CLI, `maa-cli` (Rust, repo
`MaaAssistantArknights/maa-cli`), installable on win/linux/macos via
script/homebrew/AUR/Nix/cargo. It has `maa install` (install MaaCore +
resource), `maa update` (update MaaCore + resource), `maa self update` (update
itself). Its update mechanism is DIFFERENT from the GUI: MaaCore update goes
through `api.maa.plus` + GitHub release asset + mirror speedtest
(`installer/maa_core.rs`: `browser_download_url` + mirrors); resource update
goes through **git clone** of the resource repo (`installer/resource.rs`:
`git::clone`/`git2::clone`, backend configurable, NOT MirrorChyan, NOT
tasks.json). So `maa-cli` uses NEITHER MirrorChyan NOR CDK - it's a pure
GitHub+git path, but it IS the only path that uniformly covers win+linux+macos.
mower currently does NOT use `maa-cli` (repo-wide grep for maacli/MaaCLI = 0
hits; mower loads MaaCore via Python ctypes directly).
Source: maa-cli repo tree (crates/maa-cli/src/installer/{maa_core,resource}.rs), docs.maa.plus/zh-cn/manual/cli/install.html
Verified by: source read of installer/maa_core.rs + installer/resource.rs + maa-cli docs
Stability: high
Implication: There is a THIRD architectural option for mower's update feature:
(C) shell out to `maa-cli maa update` / `maa update resource` if the user has
it installed. Pro: one cross-platform code path, no MirrorChyan/GitHub
reimplementation, no CDK needed. Con: adds an external dependency (maa-cli must
be installed and on PATH), diverges from the GUI's update source (no
MirrorChyan/CDK support at all), and mower would need to locate the maa-cli
binary. This is a real alternative to (A) but trades the user's already-chosen
MirrorChyan+CDK path for a maa-cli dependency.
