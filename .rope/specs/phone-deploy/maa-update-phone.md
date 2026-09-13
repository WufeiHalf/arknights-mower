# MAA Update on Phone (USB + laptop proxy)

## Scope

Updating MAA software + resources on the phone (Termux + proot ubuntu,
MAA at `/root/maa`). The reliable path is: **download on the laptop via
the local proxy (127.0.0.1:8118), extract & re-tar locally, push over USB
adb, run tar -xf on the phone**. In-phone direct download over the WiFi
proxy (192.168.5.9:8118) is slow/unstable and is the fallback only.

Scripts (in `my-mower-phone` repo, not this fork):
`scripts/update-maa-phone.sh` (laptop) + `scripts/update-maa-phone-onphone.sh`
(pushed to `/data/data/com.termux/files/home/` automatically, idempotent).

## Phone MAA layout & version reading

```
/root/maa/
├── libMaaCore.so, libc++.so.1, ...   # MAA 软件本体
├── maa                                # MAA CLI 可执行（调试用，mower 不用）
├── Python/asst/                       # mower import 的绑定
├── resource/                          # 完整资源（软件包自带）+ MaaResource overlay
├── cache/resource/tasks.json          # 任务缓存 OTA
└── config/                            # 用户配置（若有，软件替换时保留）
```

Version reads (both must work, verified v6.16.0):
```bash
PYTHONPATH=/root/maa/Python LD_LIBRARY_PATH=/root/maa python3 -c \
  "from asst.asst import Asst; Asst.load('/root/maa'); print(Asst().get_version())"
# 软件版本；注意 get_version 是实例方法，且必须先 Asst.load()
python3 -c "import json; print(json.load(open('/root/maa/resource/version.json'))['last_updated'])"
# 资源版本（MaaResource 的 last_updated 时间戳）
```

## Update contract

- Software: backup `/root/maa` -> `/root/maa.bak.<ts>` (rollback point),
  clear dir, `tar -xf` new package, restore `config/` + `cache/` from backup.
  MAA package may be **flat** (v6.16.0: no top-level dir) or wrapped
  (`MAA-vX.Y.Z-linux-aarch64/`) - strip top-level dir only when it is the
  single entry.
- Resource: MaaResource is a **dynamic overlay**, never replace the whole
  `resource/` (full release package's OCR/models would be lost). Extract
  with the `resource/` prefix stripped so `tar -xf` lands directly in
  `$MAA_DIR/resource/`. Also refresh `cache/resource/tasks.json`.
- After software install, the package's own `resource/version.json`
  (older) overwrites the overlay version - **run the resource step again**
  to re-apply the overlay (observed: v6.16.0 bundled 08:47:36 vs remote
  16:21:34).
- Restart mower afterwards (`mower.sh stop/start` + `adb forward`).
- Old phone script `/root/update_maa_resource.sh` (status/check/update-github/
  update-tasks-cache/sync-server/sync-maameow) remains as fallback;
  `sync-server` rsyncs `root@38.92.15.224:/opt/mower/maa/resource/`.

## Transfer path (3 steps, no direct adb push into proot)

```
adb push <file> /data/local/tmp/                  # 1
adb shell "run-as com.termux cp /data/local/tmp/<f> $TERMUX_HOME/"  # 2
proot-distro login ubuntu -- bash ...             # 3 (container reads Termux home)
```

## Recurring traps (all hit and fixed)

1. **pipefail + `grep -q` + SIGPIPE**: `tar -tf | grep -q pattern` under
   `set -o pipefail` can return non-zero (grep exits early, tar gets
   SIGPIPE) - false "self-check failed". Use `grep -c pattern >/dev/null`
   (reads the full pipe).
2. **EXIT trap referencing a function-local var** under `set -u`: the
   trap runs after the function returns -> "unbound variable". Use a
   global `WORK_TMP=""` + `trap cleanup_tmp EXIT`.
3. **tar prefix nesting**: tarring `-C dir resource` then extracting into
   `.../resource/` nests to `resource/resource/`. Strip the prefix at
   package time (`-C .../resource .`).
4. MAA tar.gz structure varies (flat vs wrapped) - detect, don't assume.

## WebUI / remote access (implemented 2026-08-02)

- WebUI: `http://127.0.0.1:58000?token=mower` (adb forward from laptop).
- **Tailscale direct** (2026-09-13, preferred when off-LAN): `adb connect
  100.98.152.81:5555` for all deploy scripts, ssh :8022 as fallback; used
  for the v6.16.0 -> v6.17.5 software update (2026-09-13, `--software`
  path, rollback point `/root/maa.bak.20260913-182331`). Details in
  `my-mower-phone/docs/operations.md`.
- External access: **autossh reverse tunnel** (Termux `remote-tunnel.sh`):
  phone -> `ssh -R 0.0.0.0:58000:127.0.0.1:58000 root@38.92.15.224` (binds
  server 127.0.0.1; `GatewayPorts` NOT needed since Nginx proxies locally).
  Reuses server Nginx `mower.kashm1r.org -> 127.0.0.1:58000` + Cloudflare
  (HTTPS). Old server-side Docker mower (which used to own :58000) was
  removed. Termux:Boot autostarts both mower and the tunnel.
- Tunnel traps: Termux has no `/usr/bin/env` - use shebang
  `#!/data/data/com.termux/files/usr/bin/bash`; `run-as` sets HOME to
  `/data/user/0/com.termux` - scripts must set HOME/PATH explicitly
  (pattern: `~/mower.sh`).
