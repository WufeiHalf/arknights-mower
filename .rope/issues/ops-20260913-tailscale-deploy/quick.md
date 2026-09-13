# Ops 2026-09-13: Tailscale full deployment + doc cleanup (rope-clear)

## Scope

Ops/deploy docs only: `my-mower-phone/{AGENTS.md,docs/*}`,
`.rope/specs/phone-deploy/{deployment,maa-update-phone}.md`.
No code/architecture changes.

## What happened (deploy session)

1. Merged upstream 4.1.5.8 (#902/#903/#904/#906) into phone/dev (36dd64115),
   then found `ui/src/pages/stage_data/event_data.json` shipped with merge
   conflict markers (fixed ee67eab07). Lesson: vite build is part of the
   merge gate.
2. Deployed mower full tree over **Tailscale adb** (`100.98.152.81:5555`),
   first run hit the `--clean` flat-extract bug (fixed my-mower-phone
   6c36c96; tree dumped flat into /root, `/start` died on TemplateNotFound
   because of the @internal=cwd contract).
3. Installed rjieba 0.2.1 offline (aarch64 wheel, laptop proxy download +
   adb push). pandas/jieba intentionally left installed.
4. Updated MAA software v6.16.0 -> v6.17.5 via `update-maa-phone.sh
   --software` over Tailscale; rollback point `/root/maa.bak.20260913-182331`.
5. Worker restarted (GET /start/0), `Maa v6.17.5 连接成功`, status working.

## Doc edits (all approved by user)

- POST->GET fixes for /start,/stop (operations.md, workflow.md, AGENTS.md)
  -- routes have no methods= (GET only, POST=405).
- Tailscale channel recorded as a deployment path (no speed numbers --
  in-LAN measurement would be misleading).
- architecture.md mower version refreshed (phone/dev@ee67eab07).
- phone-branch.md: package-and-push.sh is the established flow; added
  git-archive mirror rebuild note.
- workflow.md: dropped apply-patches.sh reference (patch-era script,
  conflicts with phone/dev single-source model; script file kept, only
  doc reference removed).
- known-issues.md #12: points to update-maa-phone.sh, old in-container
  command demoted to fallback.
- deployment.md: @internal cwd contract, --clean trap, vite build merge
  gate, offline wheel recipe.
- maa-update-phone.md: Tailscale + v6.17.5 update record.

## Verification

- `grep -rn 'X POST' docs/ AGENTS.md` -> no /start /stop POST left
- `grep -rn 'apply-patches' docs/` -> only phone-branch.md "禁止" context, none
- `grep -rn 'v6.13.0\|210189c8'` -> only historical contexts (patches/pr docs)

## Unresolved

- `scripts/apply-patches.sh` itself still on disk (user decision pending).
