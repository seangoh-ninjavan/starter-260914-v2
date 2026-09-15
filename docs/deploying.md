# Deploying — commit, push, THEN deploy

**If the deploy reports this folder isn't linked to an app**, fix it yourself before
asking anything: run `bash substrait.sh link status`, then `bash substrait.sh link apps`.
If exactly one listed app matches this project's repo, bind it
(`bash substrait.sh link use --app <slug>`) and continue the deploy. If none or several
match, show the user the list and ask which one — never guess between two apps.

Substrait builds the **pushed** branch, but it does not notice the push by itself. Three
steps, every time, in this order:

```bash
git add -A && git commit -m "describe the change" && git push
bash substrait.sh deploy
```

**Never stop after the push.** The portal's "auto-redeploys on push" label is misleading —
the deploy command is what triggers the build. Reporting "deployed" after only pushing is
the single worst mistake you can make here, because the user reloads their app, sees no
change, and has no idea why.

**Expect the deploy to refuse the first time with "uncommitted changes … scaffold_version".**
The deploy stamps `substrait.yaml` itself *before* it checks the tree was clean, so its own
edit dirties it. This is normal. Recover without asking:

```bash
git add substrait.yaml && git commit -m "stamp scaffold version" && git push
bash substrait.sh deploy
```

**Keep `openapi.json` current.** The deploy warns when it is older than your latest
`backend/` change. It is only a warning, but the file ships as the app's published API
description — so when you add, remove or rename a route, update `openapi.json` in the same
edit.

**Fallback with no terminal:** the user can open the app in the portal and click
**Redeploy** in the header.

## Checking it worked

The user can see build state in the portal under the app's **Overview → Recent
deployments**. You can confirm the push landed with:

```bash
git ls-remote origin main
git rev-parse HEAD
```

If those two SHAs match, Substrait has what it needs.

## Optional: watching the build from here

Only if the user wants live build logs in this conversation. It requires the one-time
machine link described in `docs/linking.md`, which is genuinely optional:

```bash
bash substrait.sh deploy
```

Don't set this up unless asked — pushing is enough.

## How it refuses, and what to do

| Message | Cause | Fix |
|---|---|---|
| "uncommitted changes ... scaffold_version stamp" | The deploy stamped `substrait.yaml` itself, before checking the tree was clean | Commit and push it, deploy again. Expected once after any tooling update. |
| "uncommitted changes" after linking | `SUBSTRAIT-CONTRACT.md` / `.gitignore` were just written | Commit and push, deploy again |
| "deploys from branch 'X' but you're on 'Y'" | Branch name must match exactly | `git branch -M X` or `git checkout X` |
| "local HEAD doesn't match the pushed tip" | Unpushed commits | `git push`, deploy again |
| "isn't a git checkout" | Wrong folder | Run from the repo root |
| "chose GitHub deploys but the app isn't connected" | Recorded mode vs server disagree | `bash substrait.sh link set-mode --mode connect --repo OWNER/REPO` (needs the account link) |
| HTTP 409 | Server-side SHA mismatch | Push, then deploy again |

A sign-in window during **deploy** (not push) is the `git fetch` the freshness check runs.

## After changing any API route

Update `openapi.json` in the same edit, to match what `backend/main.py` now serves. The
deploy warns when it's older than your latest `backend/` change, and warns if it's missing —
currently advisory, but slated to become a hard requirement.

### OpenAPI as the published API description

`openapi.json` at the repo root is the app's **published** API description — shown on the
portal's API tab and in the API Library. It takes precedence over the runtime harvest of the
app's own `/openapi.json`. Author it from the code; never list endpoints or fields the code
doesn't serve. Must be valid JSON with a top-level `paths` key, ≤ 1 MB.

## Deploy-mode switching

There are two deploy modes:

- **Upload** (zip) — the deploy command packages and uploads the code. The default for apps
  created without `--repo`.
- **Connect** (GitHub) — the deploy command tells the portal to pull from the pushed branch.
  Required when the workspace has zip uploads disabled.

If you hit the error **"chose GitHub deploys but the app isn't connected"**, the recorded mode
doesn't match the server. Fix it:

```bash
bash substrait.sh link set-mode --mode connect --repo OWNER/REPO
```

To create an app that is GitHub-connected from birth (required in some workspaces):

```bash
bash substrait.sh link create --name <app-name> --repo OWNER/REPO
```

See `docs/linking.md` for the full creation ladder.

## Deploy environments

An app can have more than one **deploy environment** — `production` (the default) plus e.g.
`staging` or `dev`, each with its own namespace, database, URL, variables and access settings.
Environments are created on the app's page in the portal (the environment switcher under the
header).

```bash
bash substrait.sh deploy --env staging          # deploy to staging instead of production
```

- The same folder deploys to any environment — nothing in the code changes. The app can read
  `SUBSTRAIT_ENV` (`production` | `preview`), `SUBSTRAIT_ENV_NAME` and `APP_URL` at runtime.
- Each environment has its **own** env vars and secrets. Use `--env <name>` with the env
  command too: `bash substrait.sh env --env staging list`. Creating an environment in the
  portal copies production's non-secret variables; secrets are never copied, so set them per
  environment.
- A **protected** environment (production by default) accepts deploys and variable edits only
  from the app owner or an admin.
- To pin a folder to an environment for every command, add `"environment": "staging"` to
  `.substrait/config.json`. `--env` always wins.

### Promote

Push a build from one environment to another without rebuilding:

```bash
bash substrait.sh deploy promote --to production --from staging
```

The target's database is migrated from that build's tree first, then its images are copied
and rolled out. The target must have been deployed at least once. A protected target
(production by default) accepts promote only from the app owner or an admin.

### Seed SQL

A file at `backend/db/seed.sql` is applied to **non-production** environments only — on the
first deploy, again only when the file changes, and again on the first deploy after a database
reset. Production is never seeded. Use it for test data, demo accounts, or lookup tables that
staging needs but production fills from real sources.

## `bash substrait.sh check`

Run before every deploy. Exit 0 = compliant, exit 1 = problems. It reports all of these:

- no backend Dockerfile
- `frontend/` exists but ships no frontend Dockerfile
- no `substrait.yaml`, or no `description:`, or the placeholder description
- Flyway migrations exist but no `database:` declared
- a `k8s/` directory is present

**A green check is not a deploy guarantee.** The server runs additional checks: an nginx
backend base image, unresolvable `COPY` paths, the two banned DDL shapes, a changed
database engine, and a frontend nginx config that proxies to a compose-style hostname (see
`docs/frontend.md`) are all rejected server-side.

---

## Run everything inside this editor. A separate window is a last resort.

**Run every command here, in your own command runner.** Not because it looks tidier —
because **a separate window blinds you.** You cannot read its output, so you cannot see
`! [rejected] ... fetch first`, a merge conflict, or a failed build, and you cannot recover
from any of them. The user ends up relaying error text they don't understand, badly. Run it
here and you read the error yourself and fix it.

**These NEVER need a separate window** — no exceptions:

| Command | Why it's fine here |
|---|---|
| `bash substrait.sh doctor` | prints and exits |
| `bash substrait.sh check` | prints and exits |
| `bash substrait.sh deploy` | streams the build log for ~40s, then exits |
| `bash substrait.sh link` | opens the browser itself; you relay the code |
| `git add` / `commit` / `push` | no interaction once signed in — and you need to see the errors |

### Push failures you should fix yourself, here, without asking

| Git says | What it means | Do this |
|---|---|---|
| `! [rejected] ... (fetch first)` or `(non-fast-forward)` | GitHub has commits you don't | `git pull --rebase origin main` then push again |
| `Updates were rejected because the remote contains work` | same | as above |
| `divergent branches` / `need to specify how to reconcile` | no pull strategy set | `git config pull.rebase true`, then pull and push |
| a rebase stops on a conflict | two edits to the same lines | resolve it properly (below), `git add` the file, `git rebase --continue` |

**Never leave conflict markers in a file.** If you see `<<<<<<< HEAD`, `=======` or
`>>>>>>> origin/main`, the file is broken until you remove them and the unwanted side.
`substrait.sh`, `AGENTS.md` and `SETUP.md` are tooling, not the user's work — when they
conflict, take the newer copy wholesale rather than merging line by line:

```bash
git checkout --theirs substrait.sh   # during a rebase this is the incoming version
git add substrait.sh
```

`bash substrait.sh doctor` reports any file still containing markers.

**Never `git push --force`.** If a rebase can't resolve, stop and explain — force-pushing
can destroy work that someone else, or another copy of this folder, already pushed.

### Interactive steps — when a separate window IS needed

**The one case that may need a window:** the very first `git push` on a machine that has
never signed in to GitHub. Git Credential Manager tries to show a sign-in window and cannot
do so from a sandboxed runner, so the push fails silently with no prompt.

**Escalate only after an in-editor attempt has actually failed.** Do not pre-emptively open
a window because you think one might be needed. The sequence is:

1. Run the command here.
2. If it succeeds — and it usually will, because the credential is cached after the first
   time — you are done. Say nothing about windows.
3. Only if it fails with `Repository not found` or `could not read Username` — the two
   errors that mean a credential prompt could not be shown — and you have already checked
   the four causes in `docs/github-pushing.md`, open a window. **Then immediately re-run the
   command here** so you can see the result yourself rather than relying on what the user
   reports:

```powershell
Start-Process powershell -WorkingDirectory '<FULL PATH TO THIS FOLDER>' -ArgumentList '-NoExit','-Command','git push -u origin main'
```

Use `-WorkingDirectory` rather than building a `cd '<path>';` string — a folder name with an
apostrophe, `&` or `$` breaks the quoting and the window opens on a syntax error.

**Never promise a browser window.** It only appears if they aren't already signed in. Say
what done looks like instead:

> I've opened a window. Either a sign-in page opens in your browser — approve it — or it
> just finishes, meaning you were already signed in. Either way, when the window shows
> `main -> main` it's done.

**Verify it yourself** with `git ls-remote origin` rather than waiting to be told.
