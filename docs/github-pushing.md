# Pushing to GitHub — follow this exactly, every time

Do not push a URL the user gave you verbatim. Normalise it first, and **act at each step —
don't stop and report a problem you can still fix.**

**1. Their GitHub username, once.** `git config --global github.user` — if blank, ask
*"What's your GitHub username?"* and save it: `git config --global github.user USERNAME`.

**2. Branch must be `main`** (or whatever the app is connected to): `git branch -M main`.

**3. Username in the remote URL** — this lets several GitHub accounts coexist:

```bash
git remote set-url origin https://USERNAME@github.com/ORG/REPO.git
```

**4. Verify you are NOT pointing at the starter.** Run `git remote -v` and check
the URL does NOT contain `XB-AI-Champions/substrait-starter`. If it does, you
skipped setup step 1 — go back and delete `.git`, reinit, create a new repo, and
set the remote to the user's own repo. **Never push to the starter.**

**5. Check the destination:** `git ls-remote origin`. Refs listed = good.

**6. "Repository not found"** — four causes, identical message. Work through all four
before reporting:

| Check | How | If so |
|---|---|---|
| Username missing from remote | `git remote -v` | Redo step 3 |
| Repo doesn't exist | Open `https://github.com/ORG/REPO` | 404 → create it yourself — read `docs/github-repo-creation.md` |
| Wrong account cached | Page loads, push still fails | `git ls-remote https://USERNAME@github.com/ORG/REPO` and let them sign in |
| Stale generic credential | `cmdkey /list \| findstr -i github` | `cmdkey /delete:git:https://github.com`, retry |

**7. The first push on a machine needs a real window.** Git Credential Manager's sign-in
cannot appear from inside this editor. **Launch a window for them** — see the *Interactive
steps* section in `docs/deploying.md` — never ask them to open a terminal and type. After
that first success, Windows caches the credential and every later push from here is silent.

**7b. Do not promise a sign-in window** — say what success looks like instead: "A GitHub sign-in window is about to open — that's
expected, it only happens once." No window plus instant failure means a credential problem
above, not a network one.
