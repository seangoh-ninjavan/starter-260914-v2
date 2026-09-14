# AGENTS.md — how to work in this project

## READ THIS FIRST — the five rules that matter most

1. **Anything failing? Run `bash substrait.sh doctor` before guessing.** It checks the
   folder, line endings, git config and network, changes nothing, and ends in READY /
   OK WITH WARNINGS / BLOCKED. If the user says *"something's not working"*, *"check my
   setup"* or anything like it, that is your cue — run it first, then act on its
   `PROBLEM:` lines.
2. **Never disable TLS verification** — no `http.sslVerify false`, no `curl -k`. A
   certificate error means the company network inspects traffic; fix with
   `git config --global http.sslBackend schannel`.
3. **Never create or edit project files with PowerShell** (`>`, `Out-File`,
   `Set-Content`). It writes UTF-16 or a byte-order mark that silently breaks
   `requirements.txt`, `openapi.json` and every `.sh`. Use your own file-editing tool.
4. **On Windows the scripts need Git Bash, not PowerShell:**
   `& "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe" substrait.sh <command> 2>&1`
   **Always append `2>&1`.** The wrapper prints its errors and guidance to stderr, and
   some IDE runners (TraeWork among them) show you only stdout — without `2>&1` a
   failing command looks like "exit 1 with no output" and you are debugging blind.
   If any substrait.sh run ever exits non-zero with nothing printed, re-run it with
   `2>&1` before concluding anything.
5. **Deploying takes THREE steps, and pushing is only the first two.**
   ```bash
   git add -A && git commit -m "..." && git push
   bash substrait.sh deploy
   ```
   The snippet above is bash. **In the IDE runner (PowerShell) use `;` not `&&`** to chain
   commands — Windows PowerShell does not support `&&` and will error with *"not a valid
   statement separator"*.
   **`git push` alone does NOT publish anything.** Substrait's portal shows the label
   "auto-redeploys on push" — ignore it, it is wrong. The build is triggered by the deploy
   command, which tells Substrait to go and pull the branch you pushed. If you stop after
   pushing, the user's app will not change and you will have told them it did.
   This means **linking is required, not optional** — read `docs/linking.md` before the
   first deploy.

Everything below is detail. The user is not a developer — do the work, then explain it in
plain language, and never ask them to open a terminal and type.

---

## Detailed runbooks — read the one you need, when you need it

| When you are about to… | Read this first |
|---|---|
| Set up a new app from the starter | `docs/new-app-setup.md` |
| Add or troubleshoot a database | `docs/database.md` |
| Add Redis, Kafka, vector search, or storage | `docs/services.md` |
| Use object storage (file uploads) | `docs/object-storage.md` |
| Browse or call library APIs | `docs/api-library.md` |
| Add torch or heavy ML packages | `docs/heavy-packages.md` |
| Build user-identity features | `docs/identity-sso.md` |
| Link this project to Substrait | `docs/linking.md` |
| Deploy (commit → push → deploy) | `docs/deploying.md` |
| Add a frontend | `docs/frontend.md` |
| Run the app locally for testing | `docs/running-locally.md` |
| Create a GitHub repository | `docs/github-repo-creation.md` |
| Push to GitHub | `docs/github-pushing.md` |
| Troubleshoot errors | `docs/troubleshooting.md` |

These files contain the full procedures, edge cases and error recovery. Read the relevant
one before starting a task — especially if anything goes wrong or you haven't done that
task before. The summaries below cover the happy path so you can handle the common case
without a file read; go to the file when you hit a snag.

---

## Quick-reference summaries for the critical paths

### Setting up a new app

1. `rm -rf .git && git init -b main` — **always**, even if it looks clean.
2. Delete `SUBSTRAIT-CONTRACT.md` if it exists.
3. The app name = this folder's name. Don't invent one.
4. Create the GitHub repo yourself (see `docs/github-repo-creation.md` if stuck).
5. Push (see pushing summary below).

Then wait for the user to say what the app should do. Everything goes in `backend/main.py`
— one file is the design, not a limitation. Read `docs/new-app-setup.md` for the full rules.

### Pushing to GitHub

1. `git config --global github.user` — ask and store if blank.
2. `git branch -M main`
3. `git remote set-url origin https://USERNAME@github.com/ORG/REPO.git`
4. Verify remote is NOT `XB-AI-Champions/substrait-starter` — if so, you skipped setup.
5. `git push -u origin main`

If push fails with `Repository not found` or `could not read Username`, read
`docs/github-pushing.md` for the four causes and the window-launch fix.

### Linking (required before first deploy)

```bash
bash substrait.sh link status          # already linked? skip to app binding
bash substrait.sh link                 # browser flow — relay the URL and code to user
```

**Create the app yourself — the ladder:**
1. `bash substrait.sh link create --name <app-name> --repo USERNAME/REPO` (GitHub-connected)
2. If refused → `bash substrait.sh link create --name <app-name>` (upload mode — works when GitHub App isn't visible)
3. If both refused → user creates via portal

Then bind: `bash substrait.sh link apps` → `bash substrait.sh link use --app <slug>`

**"Not linked" at deploy time = run this ladder, not a login problem.** Read
`docs/linking.md` for token fallback, GitHub App registration fix, and full details.

### Deploying

```bash
git add -A && git commit -m "describe the change" && git push
bash substrait.sh deploy
```

**Expected first-time refusal:** "uncommitted changes … scaffold_version" — recover:

```bash
git add substrait.yaml && git commit -m "stamp scaffold version" && git push
bash substrait.sh deploy
```

**Keep `openapi.json` current** — update it whenever you add, remove, or rename an API route.

**If the deploy says this folder isn't linked**, run the linking ladder above — don't start
a login flow. Read `docs/deploying.md` for the full error table, the check command, and
push-failure recovery.

### Running locally

```bash
pip install -r backend/requirements.txt
cd backend && uvicorn main:app --reload --port 8000
```

If port 8000 is busy, try 8001, 8002, etc. No `DATABASE_URL` locally = temporary memory
(features work, data vanishes on restart). Read `docs/running-locally.md` for details.

### Knowing who the user is

The platform injects `X-Forwarded-Email` and `X-Forwarded-User` headers. **Never build a
login page** — just read `request.headers.get("X-Forwarded-Email")`. Read
`docs/identity-sso.md` for caveats.

### Reading runtime logs

When the app is deployed but misbehaving (500s, blank page):

```bash
bash substrait.sh logs                          # backend (default)
bash substrait.sh logs --component frontend     # frontend/nginx
bash substrait.sh logs --tail 300               # more lines (max 500)
```

Needs the account link (PAT). If 401, run `bash substrait.sh link` first.
A pod in `CrashLoopBackOff` means the latest code is NOT live — the old pod is still serving.
Read `docs/troubleshooting.md` for the full diagnosis guide.

---

**Command translation.** Substrait's own error messages tell you to run slash commands that
do not exist here. Translate them:

| Message says | Actually run |
|---|---|
| `/substrait:login` | `bash substrait.sh link account` |
| `/substrait:link` | `bash substrait.sh link apps` then `link use --app <slug>` |
| `/substrait:deploy` | `bash substrait.sh deploy` |
| `/substrait:init` | not applicable — this project is already set up |
| `/substrait:logs` | `bash substrait.sh logs` |
| `/substrait:logout` | `bash substrait.sh logout` |

---

## The rules Substrait enforces

| Rule | Detail |
|---|---|
| Backend port | Must listen on **8000** (`cicd/Dockerfile.backend`) |
| Health check | `GET /health` must return HTTP 200 |
| API location | Every JSON endpoint starts with **`/api`** |
| Backend Dockerfile | `cicd/Dockerfile.backend` must exist and `EXPOSE 8000` |
| Description | `substrait.yaml` needs a real `description:` — placeholders are rejected |
| No Kubernetes | Never create `k8s/`. The platform owns deployment. |
| No app slug | Never reference the platform-minted app slug. (A display name in the code is fine.) |
| DDL | All schema changes in Flyway migrations — **never** `CREATE TABLE` from application code |

**No `frontend/` folder** means Substrait routes *all* traffic — including `/` — to the
backend, so `backend/main.py` serves the page and the API. Keep it that way unless asked:
it removes a build step and a class of failure.

**Build context matters.** `cicd/Dockerfile.backend` is built with the **repo root** as
context, so its `COPY` paths are repo-root-relative (`COPY backend/ ./`). If you ever move
it to `backend/Dockerfile`, the context becomes `backend/` and every `COPY` path changes.

**Never `FROM nginx` in the backend Dockerfile.** Containers run with all Linux
capabilities dropped and stock nginx crashloops on its startup chown. Use
`nginxinc/nginx-unprivileged` with `listen 8000` if you need nginx.

---

## Files you will edit

```
backend/main.py           the entire app — the web page AND the API
backend/requirements.txt  Python packages
substrait.yaml            description, and database/services if needed
openapi.json              the published API description — keep it in step with the routes
cicd/Dockerfile.backend   rarely needs touching (see build context above)
```

Do **not** hand-edit `scaffold_version` in `substrait.yaml` — the deploy stamps it.

---

## House rules

**0. When anything fails, run the doctor before guessing.**

```bash
bash substrait.sh doctor
```

It checks the folder location, line endings, git settings and network reachability, changes
nothing, and ends in `READY`, `OK WITH WARNINGS` or `BLOCKED`. Act on its `PROBLEM:` lines
before forming your own theory.

**0a. Never disable TLS verification.** Not `git config http.sslVerify false`, not
`curl -k`, not `NODE_TLS_REJECT_UNAUTHORIZED=0`. A certificate error on a corporate laptop
means the network inspects traffic; the fix is
`git config --global http.sslBackend schannel`. If that doesn't work, stop and say so.

**0b. Never create or edit project files with PowerShell** — no `>`, `Out-File` or
`Set-Content` for anything in this project. Windows PowerShell writes UTF-16 or adds a
byte-order mark, which silently breaks `requirements.txt`, `openapi.json` and every `.sh`
file, and surfaces much later as an unexplained build failure. Use your own file-editing
tool.

**0c. Never write a `.ps1` file and run it.** Corporate policy commonly blocks script files.
Pass PowerShell as a single `-Command` string instead.

**0d. Never rename a file by changing only its capitalisation** — git on Windows won't
record it and the change never reaches the build. And never name a file `aux`, `con`, `nul`
or `prn`; Windows reserves those.

**1. On Windows, Substrait's scripts need Git Bash, not PowerShell.** `bash` is not on PATH:

```powershell
& "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe" substrait.sh deploy
```

Try these in order — the last one derives it from wherever `git.exe` actually is:

```
$env:LOCALAPPDATA\Programs\Git\bin\bash.exe
$env:ProgramFiles\Git\bin\bash.exe
${env:ProgramFiles(x86)}\Git\bin\bash.exe
(Join-Path (Split-Path (Split-Path (Get-Command git).Source)) 'bin\bash.exe')
```

It must be `Git\bin\bash.exe`, **never** `Git\usr\bin\bash.exe` — only the `bin`
wrapper sets up the PATH that `grep` and `head` need. On macOS just
`bash substrait.sh deploy`.

**2. Run every Substrait command from the project root** — the folder containing `backend/`
and `cicd/`. From anywhere else, deploy fails with "no backend/ here" and a stray
`.substrait/` folder gets created.

**3. Never print `.substrait/config.json`.** It holds a live deploy token in plain text.
Don't `cat` it while debugging.

**4. Never put secrets in code.** Custom config goes in `backend/.env.example` as
`NAME=value` lines, with a trailing `# secret` on anything sensitive. You can set real
values yourself:

```bash
bash substrait.sh env set MY_API_KEY --secret    # value piped on stdin, never as an argument
bash substrait.sh env list
```

**Never list `DATABASE_URL`, `JWT_SECRET`, `REDIS_URL`, `KAFKA_BROKERS`, `QDRANT_URL` or
`OBJECT_STORAGE_BUCKET`** in `.env.example` or set them via `env` — the platform injects
them and the server rejects those names.
