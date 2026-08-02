# Game Data Refresh Pipeline (新干员数据更新)

## Scope

How to add support for new operators / refresh recognition data when the
game resource submodule (`ArknightsGameResource`) gains new content.
Applies to both upstream data updates (like 机械师 #899) and phone-only
updates (予愿安洁莉娜/珊比/嘉辛塔/时隙, commit `5f779a602`).

## Pipeline

```
1. Update submodule:  ArknightsGameResource -> latest commit
2. Run auto_get_res_new.py (full script, order matters):
     添加物品 -> 添加干员 -> 读取卡池 -> 读取活动关卡
     -> 批量训练并保存扫仓库模型 -> 干员名模型 x3 -> auto_fight_avatar
     -> 获得干员基建描述 -> buff转换 -> 添加基建技能图标
     -> load_recruit_resource -> 获取加工站配方类别 -> 提取专精数据
3. Run build_assets.py ensure_skill_data_extracted()
   (regenerates resources/skill_data.json for the packaged asset dir)
4. Verify (see Checks below), then commit submodule + data together
```

Deps: `venv` with cv2 / skimage / sklearn / PIL (verified working),
fonts at `arknights_mower/fonts/`, `ui/node_modules` not required.

## Output files & generators

| 文件 | 生成器 |
|------|--------|
| `data/agent.json`, `data/agent_profession.json` | 添加干员 |
| `data/key_mapping.json` + `ui/public/depot/*.webp` | 添加物品（含信物，自动） |
| `ui/public/avatar/*.webp` | 添加干员（无条件重存，字节可能变） |
| `data/recruit.json` / `recruit_result.json` | load_recruit_data（公招池变化） |
| `models/NORMAL.pkl` / `CONSUME.pkl` | 批量训练并保存扫仓库模型 |
| `models/operator_room/select/train.model` | 干员名模型（字体渲染，无截图） |
| `models/avatar.pkl` | auto_fight_avatar（avatar/*.png 缩小） |
| `models/recruit_result.pkl` | load_recruit_resource（FZDYSK 渲染） |
| `data/stage_data_full.json`, `stage_order.json`, `ui/src/pages/stage_data/event_data.json` | 读取活动关卡 |
| `ui/src/pages/basement_skill/skill.json` / `buffer.json` | 获得干员基建描述 / buff转换 |
| `data/workshop_formula.json` | 获取加工站配方类别 |
| `data/skill_data.json` | 提取专精数据 |
| `resources/skill_data.json` | build_assets.py ensure_skill_data_extracted |

## External dependencies / traps

### FZDYSK.TTF (recruit_result.pkl)
`load_recruit_resource` renders recruit-result name templates with
`FZDYSK.TTF` (方正大黑简体, author's local Windows font - not in repo).
When the font is missing the step fails and the pkl is NOT regenerated.

Strategy when only pool additions (e.g. 羽毛笔/水月 enter the pool):
keep the 158 existing templates byte-identical and **append** the new
renders (FZDaHei-B02 family via 方正大黑_GBK.ttf). CJK glyphs are stable
across FZDaHei versions (~0.85 CCORR aligned); ASCII/Latin glyphs are not
(0.49) - so only append all-CJK names. Appending is strictly better than
missing templates (max-score matching never regresses).

### composite_table.v2.json (skill_data composite)
`提取专精数据` reads `frontend-v2-plus-dev/src/static/json/material/
composite_table.v2.json` (from MAA's old frontend repo - **no longer
available upstream**, 404 on dev/dev-v2/archive branches). Without it
`composite_count` drops to 0 (regression: was 27).

Recovery: the old `data/skill_data.json` contains the `composite` dict;
convert it back into the list-of-entries format the script expects
(`itemId/itemName/rarity/resolve:false/pathway[{itemId,itemName,count}]`).
The composite data is stable (workshop synthesis recipes don't change).

### avatar webp byte noise
`添加干员` re-saves every avatar unconditionally. With current PIL/libwebp
the bytes differ but **pixels are identical**. To keep the diff minimal:
`git checkout -- ui/public/avatar/` and keep only the newly-added files.
Verify with pixel compare (np.array_equal), not byte compare.

## Checks before commit

- `agent.json` / `agent_profession.json` contain the new names
- `key_mapping.json` has `<name>的信物` entries
- `skill_data.json` (both data/ and resources/) characters include new
  chars with non-empty `materials`; `_meta.composite_count` stays 27
- `ui/src/pages/basement_skill/skill.json` includes new operators (and any
  manual supplements like 机械师's descriptions survive regeneration)
- model additive check: old vs new pkl - `operator_*.model` should be
  added-only; `avatar.pkl` may legitimately change existing entries
  (skins updated in newer submodule data)
- `recruit_result.pkl` old entries unchanged (when appending)
- `python -m unittest discover -s arknights_mower/tests -p "*_tests.py"`
  and `ruff check .` / `ruff format --check .`

## Phone deployment

Phone gets the same data via `package-and-push.sh` full-tree deploy
(phone/dev). No separate data-only push path.
