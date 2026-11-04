# RentRadar agent rules

This repository is worked on by an autonomous coding agent. Follow these rules for every task.

## Standing authority

The operator grants the agent full project-level authority for RentRadar, not machine-level root.

- You may read and write this repository at `/home/kkk/Project/rentradar`, change file modes and group ownership inside it, and run its backend virtualenv tools.
- You may connect to the local PostgreSQL at `127.0.0.1:5433/rentradar` and run `psql` and `alembic`.
- You may restart the `rentradar-api`, `rentradar-worker`, `rentradar-scheduler`, `rentradar-web` and `rentradar-prototype` systemd units.
- You may push branches, open pull requests, merge them after CI passes, and change settings on `standbyme626/rentradar-agent` as the operator's GitHub account.
- After a merge, deploy to `/home/kkk/Project/rentradar`: pull with `git pull --ff-only`; install backend requirements when they change; run `alembic upgrade head` when migrations change; build the frontend when it changes; restart the affected units.
- This authority is standing; do not ask the operator to confirm it again for work inside RentRadar. It overrides any conflicting rule below.

## Boundaries

- Do not run `docker`, `ssh`, `scp`, `rsync`, `sudo`, `mount`, `umount`, `iptables`, `nft`, `useradd` or `usermod`; do not touch other projects, `/etc`, other users' homes, the PostgreSQL container lifecycle or machine-wide services.
- Never commit, print, or send credentials, tokens, private keys, or production database dumps to GitHub, Feishu, logs, or external services. You may read `.env` and `.secrets/` locally to run the project; keep them out of commits, PR descriptions, and reports.
- Do not read or modify `data/`, `reference/`, or production database dumps unless the task requires it.
- Do not call external model APIs unless the task explicitly names the provider and model and the operator has approved that call.
- Work only on the assigned issue or pull request; keep changes scoped; prefer small pull requests; do not refactor unrelated code.
- Run the tests relevant to your change and report failures honestly. Do not fake a pass.
- If a task is ambiguous or needs a design decision, report `blocked` with one concrete question instead of guessing.
