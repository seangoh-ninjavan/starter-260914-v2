# Troubleshooting

**Browser authorisation succeeds but `link status` still says "No account link".** The
editor's sandbox blocked writing the credential to `~/.substrait`. `substrait.sh` detects
this and redirects the credential into the tooling folder automatically — make sure you ran
the link through `bash substrait.sh link` (never the plugin scripts directly), and just run
it once more. Do not ask the user to change editor permission settings; that path has been
tried and doesn't work reliably.

**First Substrait command seems to hang.** It's downloading the tooling into
`~/.substrait-tools`. Run it again.

**`link apps` errors with "no account link on this machine".** Run `bash substrait.sh link`
first — `apps`, `repos` and `set-mode` all need the account link.

**`$'\r': command not found` / `syntax error near unexpected token`.** Windows line
endings. Run `sed -i 's/\r$//' substrait.sh`, then `git config --global core.autocrlf input`
so it doesn't recur.

**`Permission denied` or `Unable to create '.git/index.lock'` on a file they can clearly
edit.** OneDrive is holding the file. The folder must be moved out of OneDrive — pausing
sync only helps until it resumes. See SETUP.md Step 0.

**`! [rejected] main -> main (non-fast-forward)`.** Another copy of this folder was pushed
first. Find the other copy — do **not** force-push, it will destroy their work.

**"link expired or was not approved in time".** Usually this editor's runner killing the
command mid-wait, but **check the machine clock too** — if it's more than a few minutes off,
the token really is rejected as expired, and no amount of retrying helps.

**Everything fails with "could not reach https://api.substrait.build".** Check whether they
need to be on the company VPN. Never work around it by disabling certificate checks.

**`echo: write error: Bad file descriptor` from any `substrait.sh` command.** The IDE runner
closed the output pipe before the script finished. The command **still ran** — the output
just didn't reach you. The script automatically saves a complete log every time it runs.
**Read `.substrait-last-run.log` in the project folder** — it has the full output. Act on
what the log says; do not retry the command just because the runner showed an error.

This is not a Substrait problem, not a linking problem, and not an auth problem. Don't
diagnose it, don't ask the user about it — just read the log file.

**Never fall back to running the scripts in PowerShell.** They are bash and will not work.

---

## App deployed but showing 500s or a blank page

The deploy went green but the app is misbehaving. Use `bash substrait.sh logs` to read the
pod logs — this is the window that the deploy's `--watch` cannot reach (it stops at
PREVIEW_LIVE).

```bash
bash substrait.sh logs                          # backend log (default, where 500s originate)
bash substrait.sh logs --component frontend     # frontend/nginx log (blank page, 502)
bash substrait.sh logs --tail 300               # more lines (max 500)
bash substrait.sh logs --previous               # last terminated instance's log
```

**Needs the account link (PAT), not the deploy token.** If you get a 401, run
`bash substrait.sh link` first — don't re-link the app, re-link the account.

**What to look for:**

- **CrashLoopBackOff** on a pod means the latest code is **NOT live** — the old pod is still
  serving while the new one crashes. The app looks alive but the latest deploy hasn't landed.
  Say so plainly.
- **`--- previous (terminated) instance ---`** means the container isn't running now — you're
  reading the log from just before it died. That is usually where the real error is.
- **Read the deepest application frame** in a Python traceback — the file and line inside your
  app, not inside the framework. A 500 is almost never the framework's fault.
- If the pods are healthy and the log shows nothing at the time of the failure, say that —
  the request may not be reaching the app at all. Don't invent a cause.
