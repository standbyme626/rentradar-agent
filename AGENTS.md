# RentRadar agent rules

This repository is worked on by an autonomous coding agent. Follow these rules for every task.

- Work only on the issue or pull request you were assigned. Do not push to `main`; open a pull request and stop.
- Never read, print, modify, or commit `.env`, `.secrets/`, `data/`, `reference/`, credentials, tokens, private keys, or production database dumps.
- Do not run `systemctl`, `docker`, `psql`, `alembic upgrade`, `ssh`, `scp`, `rsync`, or `sudo`. The operator runs production services.
- Do not call external model APIs unless the task explicitly names the provider and model and the operator has approved that call in the issue.
- Keep changes scoped to the issue. Prefer small pull requests; do not refactor unrelated code.
- Run the tests relevant to your change and report failures honestly. If a test cannot run because a service or credential is missing, say so; do not fake a pass.
- Do not enable auto-merge and do not merge pull requests.
- If the task is ambiguous or needs a design decision, report `blocked` with one concrete question instead of guessing.
