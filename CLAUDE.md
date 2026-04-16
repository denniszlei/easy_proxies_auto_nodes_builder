# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository scope

This repository is a small Python-based generator that builds an `easy_proxies`-compatible `nodes.txt` artifact from public proxy sources.

The repository no longer contains a local checkout of `easy_proxies`. Treat `easy_proxies` as an external compatibility target referenced by the user/README:
- https://github.com/jasonwong1991/easy_proxies.git

Do not assume any local `referrence/` directory exists.

## Current repository structure

- `scripts/build_nodes.py` — the only generator script; fetches sources, filters to supported URI schemes, deduplicates, sorts, and writes artifacts
- `dist/node.txt` — generated artifact published from this repo
- `dist/metadata.json` — generated metadata summary
- `.github/workflows/build-node-list.yml` — scheduled workflow that regenerates and commits the artifacts
- `README.md` — public-facing usage and download instructions

Keep the implementation simple. Prefer extending `scripts/build_nodes.py` over introducing extra modules unless the script becomes clearly unwieldy.

## Common commands

### Generate artifacts locally
```bash
python3 scripts/build_nodes.py
```

### Inspect generated outputs
```bash
python3 - <<'PY'
from pathlib import Path
for path in [Path('dist/node.txt'), Path('dist/metadata.json')]:
    print(path, 'exists=', path.exists(), 'size=', path.stat().st_size if path.exists() else 0)
PY
```

### Show current git changes
```bash
git status --short
```

## Architecture

### Data flow
- `scripts/build_nodes.py` fetches two public sources:
  - subscription text from `https://imtaqin.id/api/vpn/sub/all`
  - JSON proxy data from `https://imtaqin.id/api/proxies`
- Subscription lines are treated as authoritative URI inputs and are preserved when already compatible.
- JSON proxy rows are converted into `socks5://...` or `http://...` URIs.
- Results are filtered to the URI schemes that `easy_proxies` actually supports in practice, then deduplicated and sorted before writing `dist/node.txt`.
- `dist/metadata.json` records generation time, source info, and protocol counts.

### Compatibility boundary
This repo does not implement proxy parsing itself beyond lightweight normalization. Its contract is: output plain-text `nodes.txt` where each line is a URI that `easy_proxies` can consume.

When changing compatibility logic, align with the external `easy_proxies` project's actual builder support rather than broader URI recognition examples.

### Publishing model
- Generated artifacts are committed into the repository.
- GitHub Actions runs on a 6-hour schedule and on manual dispatch.
- The workflow commits only the generated files when they change.

## Important implementation details

- Prefer Python standard library solutions unless a dependency is clearly necessary.
- Keep generated artifacts deterministic: stable filtering, stable dedupe, stable sort order.
- `dist/node.txt` is a committed build artifact, not a throwaway temp file.
- Be careful when changing naming, sorting, or dedupe rules because they directly affect downstream diffs and published raw URLs.
- The `https` boolean in the JSON proxy source should not be treated as proof that the proxy URI scheme should be `https://`; current behavior intentionally emits `http://` for JSON HTTP proxies unless the source semantics are known to require TLS at the proxy endpoint.

## Workflow guidance

If you modify `scripts/build_nodes.py`, usually also:
- run it locally to refresh `dist/node.txt` and `dist/metadata.json`
- review the artifact diff for accidental churn
- update `README.md` only if user-facing behavior changed

If you modify `.github/workflows/build-node-list.yml`, keep the workflow focused on:
- checkout
- setup Python
- run the generator
- commit generated artifacts only when changed

## External dependency note

Because `easy_proxies` is no longer checked into this repository, future compatibility verification against its runtime can only be done if the user provides a separate local checkout or asks you to work against the upstream repository explicitly.
