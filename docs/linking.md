# Linking this project to its Substrait app — REQUIRED

`bash substrait.sh deploy` cannot work until this machine is linked and this folder is
bound to the app. Do this once per machine and once per project, before the first deploy.

**The app must exist before the first deploy. Create it yourself — the CLI creation
ladder, in this order.** The app name is this folder's name (see `docs/new-app-setup.md`).
A successful create also binds this folder, so step 2 below is then
already done.

**Rung 1 — GitHub-connected from birth** (best when it works: pushes become the deploy
source). With the machine linked (step 1) and the repo pushed:

```bash
bash substrait.sh link create --name <app-name> --repo USERNAME/REPO
```

**When rung 1 is refused ("not installed" / "repo isn't reachable"), the usual cause is
Substrait's registry, not GitHub — and the fix takes the user 30 seconds.** Substrait
only learns about a GitHub App installation when GitHub sends it an event, and that
record can be missing or stale even while github.com shows the app installed with "All
repositories". Have the user do this (it works even when the setting ALREADY says All
repositories — clicking Save re-sends the registration): github.com → Settings →
Applications → Installed GitHub Apps → Substrait → **Repository access** → switch to
"Only select repositories", switch straight back to "**All repositories**", click
**Save**. Then retry rung 1 once — the repo should now appear in `link repos`. Never
suggest uninstalling the GitHub App, and never debug accounts: a repo missing from
`link repos` is not evidence of a wrong account, and you must never propose recreating
the repo under a different account.

**Rung 2 — if rung 1 is still refused (or the user isn't there to click), create the
app WITHOUT the repo:**

```bash
bash substrait.sh link create --name <app-name>
```

This makes an **upload-mode app**: `bash substrait.sh deploy` then packages this folder
and uploads it directly — no GitHub App involvement at all, which is exactly why this
rung works even when `link repos` can't see the repo. Keep pushing to GitHub exactly as
before (the repo stays the master copy); only the deploy transport differs, and the app
can be switched to GitHub deploys later with `link set-mode` once the installation is
visible. Do not treat rung 1's failure as a problem to solve first — a repo missing from
`link repos` is not evidence of a wrong account or a broken install; never debug
accounts, never loop asking which account is right, and never propose recreating the
repo under a different account. Go straight to rung 2 and ship.

**Rung 3 — only if rung 2 is ALSO refused** (a workspace with zip uploads disabled):
tell the user to open app.substrait.build → **Build** → **Connect GitHub** → pick the
repo (goes straight to the picker after the first time, ~45 seconds), then bind with
step 2 and deploy.

**"Not linked" at deploy time is THIS ladder, not a login problem.** If
`substrait.sh deploy` reports the folder isn't linked to an app (or `link status` shows
the machine linked but no app bound), the machine link from the pre-work is fine — the
project simply has no app yet. Run the creation ladder above immediately, yourself; do
NOT start a browser "link"/login flow, and do NOT ask the user to link anything.
And never take `SUBSTRAIT-CONTRACT.md` as evidence the folder is linked: the real
binding is the gitignored `.substrait/config.json`, which never arrives with a clone.
A `SUBSTRAIT-CONTRACT.md` naming `substrait-starter` is a stale copy from the starter —
delete it; linking rewrites it correctly.

## Step 1 — link this machine (browser). This is the normal way.

```bash
bash substrait.sh link status     # already linked? then skip to step 2
bash substrait.sh link            # authorise this machine — once per machine
```

**Run it so the user can see the output — never redirect it to a file, never pipe it,
never hide it.** It prints a URL and a verification code, opens the browser, then blocks
while it waits for approval. The blocking is expected; do not kill it.

**Relay the URL and the code to the user as text the moment they appear**, even though the
browser should open by itself:

> Open this link now and approve it — I'm waiting for you.

Nothing secret changes hands in this flow, which is why it's the default.

**Run it in a launched window, not from here** — see the *Interactive steps* section in
`docs/deploying.md`. This editor's runner kills long waits, and the browser cannot open
from it. If you have already tried it here and got *"link expired or was not approved in
time"*, that is the runner killing it, not a real expiry — open a window and run it there
instead. Only if that also fails, fall back to step 1b.

## Step 1b — fallback: link with a token

Only if the browser flow above was killed or keeps reporting expiry.

**Ask the user to mint the right kind of token.** There are two kinds and only one works:

> In app.substrait.build, use **Access tokens in the left sidebar** — *not* the Access
> tokens section inside an app. Click **Create token**, give it any name, and copy what it
> shows you. It's only shown once.

| Where they get it | Starts with | Scope |
|---|---|---|
| Left sidebar → **Access tokens** ✅ | `sbt_` | Every app they own — this is the one you need |
| An app's **Deploy** tab ❌ | `sbd_` | That single app only — `save-account` rejects it |

**Check the prefix.** If it starts with `sbd_`, tell them they took it from the app's Deploy
tab and need the sidebar page instead.

**Have them put it in a file, not in this chat:**

> Save it into a file called `token.txt` in this project folder — paste it into Notepad and
> save. Don't paste it into our conversation.

This keeps the secret out of the chat transcript, which the editor's vendor may store.
`token.txt` is already in `.gitignore`.

```bash
bash substrait.sh link save-account --token "$(cat token.txt)" --portal-url https://api.substrait.build
rm token.txt
```

Never print the token, never echo it back, never `cat token.txt` on its own.

## Step 2 — bind this folder to the app

```bash
bash substrait.sh link apps               # lists "slug<TAB>name" — show the names to the user
bash substrait.sh link use --app <slug>
```

**Reading `link status`:** its first line says "No account link on this machine" whenever
there's no personal token. **Read the last line**, not the first.

**Linking writes files** — `SUBSTRAIT-CONTRACT.md`, and a line in `.gitignore`. That dirties
the tree, so commit before deploying (the deploy runbook in `docs/deploying.md` covers it).

Use `link account` for authorisation, not `link login`. `login` mints an app-scoped token
that cannot run `apps`, `repos` or `set-mode`.
