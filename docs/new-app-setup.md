# Setting up a new app from the starter — the whole job is yours

When the user says anything like *"set up a new Substrait app in this folder from the
starter"*, do ALL of the following without sending them anywhere:

1. **Delete `.git` and start fresh — this is not optional.**
   The starter's `.git` folder points at `XB-AI-Champions/substrait-starter`.
   If you keep it, every push sends this user's code into the shared starter
   repo. **Always run this, even if you think it's already clean:**
   ```bash
   rm -rf .git && git init -b main
   ```
   Also delete `SUBSTRAIT-CONTRACT.md` if the starter brought one — it records
   the STARTER project's own link ("Linked app: substrait-starter") and is stale
   here. Linking this project recreates it with the right app.
2. **The app is named after this folder.** The folder's name is the repo name and the
   app name (one app = one folder = one repository — the folder IS the app). Do not
   invent a different name and do not ask for one; the user chose it when they named
   the folder.
3. **Create the private GitHub repository yourself** — read `docs/github-repo-creation.md`.
   Never send the user to github.com for this.
4. **Push everything** using `docs/github-pushing.md` (username-in-remote, `main`).
5. Confirm in one short message: repo name, the account it was created under, pushed.

Then wait for the user to describe what they want the app to do.

**Build small, build fast.** When you then build or change the app: everything lives in
`backend/main.py` plus at most one new Flyway migration per change — no extra modules,
packages, helper files, config files, and no `frontend/` folder. Do not restructure the
starter and do not spend time re-reading every project file; `backend/main.py`,
`substrait.yaml` and the migration folder are the whole picture. One file is the design,
not a limitation — it is what keeps builds fast and deploys simple. Write the code in as
few passes as you can rather than many small exploratory edits.

One file caps the LAYOUT, never the ambition: build everything the user asked for, at
the quality and polish they asked for, inside that one file — never trim a feature or
simplify the design to stay small, and never keep or imitate the starter's example page
because it happens to be there. A full app with a rich page fits comfortably in one
`main.py`. If something genuinely won't fit well, say so and ask — don't quietly shrink
it.
