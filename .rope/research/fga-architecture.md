# FGA (Fate-Grand-Automata) Architecture Reference

## Source

GitHub: <https://github.com/Fate-Grand-Automata/FGA>
Verified: 2026-07-13 (README + AndroidManifest.xml)

## How FGA Runs on Phone Without Root

FGA is a **native Android app** (Kotlin), not a script-over-ADB like
mower. It uses three Android system APIs that don't require root:

| Function | API | mower's equivalent |
| ---------- | ----- | -------------------- |
| Screenshot | **MediaProjection** (`android.media.projection.MediaProjection`) | `adb screencap` (remote, slow) |
| Click/Swipe | **AccessibilityService** (gesture dispatch) | `maatouch` over ADB |
| Keep-alive | **Foreground Service** + notification + battery opt-out | Termux proot (killed by Android easily) |

## Why FGA Doesn't Get Killed

From `AndroidManifest.xml`:

```xml
<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_MEDIA_PROJECTION" />
<uses-permission android:name="android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS" />

<service android:name=".runner.ScriptRunnerService"
         android:foregroundServiceType="mediaProjection|specialUse" />

<service android:name=".accessibility.TapperService"
         android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE" />
```

Three layers of protection:

1. **Foreground Service** (`ScriptRunnerService`): once started, Android
   gives high priority + notification bar icon. System won't easily kill.
2. **Accessibility Service** (`TapperService`): highest priority once
   enabled. Almost unkillable.
3. **Battery optimization exclusion**: user grants via
   `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`.

## Tech Stack

- Language: Kotlin
- Image recognition: OpenCV (bundled)
- UI: Native Android (XML layouts + ViewModels)
- Build: Gradle (Android Gradle Plugin)
- Min SDK: Android 7+ (API 24+)

## Comparison with Mower

| Aspect | FGA | mower |
| -------- | ----- | ------- |
| Logic complexity | Simple (auto-battle scripts) | Complex (scheduling, 排班, 专精, mood tracking) |
| Image assets | ~30 templates | 100+ templates + OCR models |
| Architecture | Native app, self-contained | Python + Flask + ADB + optional MAA |
| Keep-alive | Foreground Service (rock solid) | Termux proot (fragile) |

FGA can be native because its logic is simple. Mower's logic (4000+
line `base_schedule.py`, scene graph solver, 排班, 专精 system) makes a
full Kotlin port impractical (months of work).

## Viable Path for Mower: Native Shell + Python Core

A native Android helper app that only handles "eyes and hands", while
mower's Python business logic stays unchanged:

```
Native app (Kotlin)
├─ MediaProjection screenshot -> local socket
├─ AccessibilityService -> receives coords from Python, dispatches taps
├─ Foreground Service keep-alive + notification
└─ (optional) embeds Python via Chaquopy

Termux Python (or embedded)
├─ mower business logic (unchanged)
├─ OpenCV template matching (unchanged)
└─ device/ layer: swap ADB backend for local-socket backend
```

Effort: 2-4 weeks. Only `arknights_mower/utils/device/` abstraction
layer changes; all solver/business logic reuses as-is.

## Why Termux proot Gets Killed

Termux runs as a normal Android app. proot-distro launches a Linux
container inside it, but it's still a "normal background process" from
Android's perspective. Android's memory management / battery optimizer
kills it under memory pressure or after screen-off periods.

No amount of `nohup` / `setsid` / `disown` fully fixes this. The only
reliable solutions are:

1. Foreground Service (requires a native app, like FGA)
2. Accessibility Service (same)
3. Termux:Boot + battery-opt-out (reduces frequency, doesn't eliminate)
