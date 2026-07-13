# Depot Inventory Data Freshness

## Scope

The "数据图表 -> 仓库" (depot) view in WebUI shows material counts
that can be **stale**. This affects workshop scheduling decisions
(`self_upper_limit` checks) and user trust. Verified by direct API
calls on 2026-07-13.

## Data Sources

| Source | What | Refresh | Used By |
| -------- | ------ | --------- | --------- |
| `tmp/cultivate.json` | Skland API snapshot of player inventory + characters | `cultivate().start()` (Skland login -> GET cultivate/player) | `/depot/readdepot`, `self_upper_limit` checks, `_auto_complete_level3` |
| `tmp/depotresult.csv` | In-game OCR depot scan history | `DepotSolver` (仓库扫描 task) | `/depot/readdepot` (merged with cultivate.json) |
| `inventory` table in `data.db` | Material counts keyed by workshop_formula id | `save_inventory_counts()` (called from `读取仓库()` and `depot.py`) | `try_workshop_tasks`, `plan_solver` workshop scheduling |

## The Problem

`/depot/readdepot` (server.py:248) is **read-only** -- it reads
`cultivate.json` and `depotresult.csv` but never triggers a refresh:

```python
def 读取仓库():
    path = get_path("@app/tmp/cultivate.json")
    with open(path) as f:          # just reads, no refresh
        depotinfo = json.load(f)
    ...
    return [classified_data, ..., str(time)]
```

`cultivate.json` is only refreshed by `cultivate().start()`, called at:

- `MasterySync._refresh_skland_data()` (every MasterySync run)
- `generate_product()` (start of each workshop task)
- `仓库扫描()` / `DepotSolver`

If mower isn't running, or these refresh points fail (e.g. transient
DNS failure to `zonai.skland.com`), `cultivate.json` stays stale.

## Verified Example (2026-07-13)

```
Skland API (live):    切削原液 = 6    (user synthesized 6 last night)
cultivate.json:       切削原液 = 3    (stale snapshot from 08:32)
UI 显示:              切削原液 = 3    (wrong)
```

After calling `cultivate().start()` manually, `cultivate.json`
updated to 6. So the API is correct; the local cache was just not
refreshed.

## Impact on Workshop Scheduling

`self_upper_limit` and `children_lower_limit` checks
(`base_schedule.py:1222`, `scheduler_task.py:544,572`) read
`inventory_data`, which comes from `cultivate.json` (via
`save_inventory_counts`).

If `cultivate.json` shows 3 when the real count is 6, mower will
schedule another workshop task to synthesize 3 more (thinking it's
below the limit), over-producing.

## `self_upper_limit` Config Contract

In `workshop_settings` (conf.yml), each item has:

| Field | Meaning | Check |
|-------|---------|-------|
| `self_upper_limit` | **target material** stock ceiling | `库存 < 上限` -> trigger synthesis |
| `children_lower_limit` | **sub-material** stock floor | `子材料库存 > 下限` -> safe to synthesize |

`self_upper_limit` is NOT a game warehouse capacity limit (the game has
no such limit). It's the target stock level mower maintains. Default 30.
UI help-text "设置占位，可能没用" is misleading -- it IS used.

## Skland API Sync Delay

Even when `cultivate().start()` succeeds, the Skland API itself has a
sync delay (minutes to tens of minutes) after in-game operations.
So refreshing immediately after `craft_material` may still return old
counts. This is an external constraint mower can't fix.

## Potential Fixes (not yet implemented)

1. `/depot/readdepot` accepts `?refresh=1` to trigger
   `cultivate().start()` before reading. Risk: API rate limit + the
   sync delay means fresh data isn't guaranteed.
2. Show `cultivate.json` mtime in UI so user knows snapshot age.
3. `craft_material` calls `cultivate().start()` after completion. May
   still hit API sync delay.

## Key Files

- `server.py:248`: `/depot/readdepot` route (read-only)
- `arknights_mower/utils/depot.py`: `读取仓库()` + `save_inventory_counts()`
- `arknights_mower/solvers/cultivate_depot.py`: `cultivate.start()`
  (Skland API fetch -> writes `cultivate.json`)
- `arknights_mower/utils/config/conf.py`: `WorkshopItem` model
  (`self_upper_limit`, `children_lower_limit`)
- `arknights_mower/solvers/base_schedule.py:1222`: workshop material
  check using `self_upper_limit`
- `arknights_mower/utils/scheduler_task.py:544,572`: same check
