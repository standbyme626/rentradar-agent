# P0 UI evidence (2026-11-04)

Before/after captures for the P0 frontend changes:

- `before-*` — `main` at `5703011` (extracted with `git archive main`).
- `after-*` — this branch.
- Same scenario, 1440×900 viewport, light theme, local mock API.

The agent has no production database access, so the app was run locally against
a small mock API serving the same listing/detail/watchlist payloads for both
revisions. The screenshots therefore show the real SPA components and real
routing/state transitions, not production data; this limitation is stated in
the PR.

| File | Shows |
|---|---|
| `before-chat-header.png` / `after-chat-header.png` | user chat header; after adds the 看房清单 entry |
| `before-detail-top.png` / `after-detail-top.png` | listing detail; before has fixed 35/25/13/8/5/5 bars and placeholder image tiles, after shows `score_reasons.components`, real p50/p90, real price points |
| `after-detail-ledger.png` | real price curve, delivery probe, checklist/notes/photos in the detail drawer |
| `after-ledger.png` | 看房清单 drawer with state/checklist/notes/CSV export |
| `before-admin-tasks.png` / `after-admin-tasks.png` | admin tasks; after adds per-station shard coverage panel and 10/180 shard rotation |
| `before-admin-commute.png` / `after-admin-commute.png` | admin commute; after switches to SZMC zero-quota copy and p50/p90 columns |

The mock API and Playwright script were local tooling and are not committed.
