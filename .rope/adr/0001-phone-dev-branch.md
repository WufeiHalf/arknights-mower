# phone/dev: Long-Lived Phone Integration Branch

## Context

The fork (`WufeiHalf/arknights-mower`) deploys to an Android phone for
real-device testing. The phone needs environment-specific patches
(start mutex, asst path priority) that should NOT go to upstream PRs.

Previously, patches lived only on the phone's filesystem or in the
`my-mower-phone` meta-repo's `patches/` directory. Deploying feature
code by overwriting individual files clobbered these patches, causing
repeated regressions (lost start lock, MAA connect failure).

## Decision

Create a long-lived branch `phone/dev` on `origin` (WufeiHalf fork)
that contains: `upstream/dev` + phone-only environment patches + any
feature currently under real-device test.

- Feature branches always branch from `upstream/dev` and PR back to
  `upstream/dev`. They never branch from `phone/dev`.
- Before deploying to phone, merge the feature into `phone/dev`.
- `phone/dev` never opens PRs to `upstream`.
- After upstream merges a feature, `phone/dev` merges `upstream/dev` to
  absorb it, preserving phone-only commits.

## Branch Naming

Cannot use `dev/my-phone` because `origin` already has a branch named
`dev`. Git cannot have both `refs/heads/dev` and `refs/heads/dev/my-phone`
(ref namespace conflict). Use `phone/dev` (prefix style, no conflict).

## Deployment

Use full-tree deployment from `phone/dev` via
`my-mower-phone/scripts/package-and-push.sh`. Never overwrite
individual files from feature branches. See
`.rope/specs/phone-deploy/deployment.md` for details.

## Consequences

- Phone-only patches are version-controlled, not folklore.
- Deploying to phone is reproducible from a known commit.
- `my-mower-phone` meta-repo is demoted to scripts + docs; its `mower/`
  mirror is a deployment snapshot, not the source of truth.
- All 17 historical patches from `my-mower-phone/patches/` have been
  merged into `phone/dev` (via fix branch merges + manual application).
