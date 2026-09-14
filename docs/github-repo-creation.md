# Creating a new GitHub repository — do it yourself

Never send the user to github.com to create a repository. Create it for them using the
Git credential already cached on this machine.

**Establish the username first** (`git config --global github.user`; ask and store it if
unset — same rule as `docs/github-pushing.md`).

**State the target account BEFORE creating, every time:**

> I'll create the private repository **REPO** under the GitHub account **USERNAME** —
> tell me now if it should go somewhere else.

Take the username from the credential you are about to use, not from guesswork. If the
credential's username and `github.user` disagree, stop and ask which account is intended.

**If the user chooses an account that has no cached credential on this machine**, get one
— two ways, in order:

1. **Git's own sign-in (preferred — nothing to install).** Put the chosen username in the
   remote URL (`docs/github-pushing.md`, step 3) and run a remote operation — Git Credential
   Manager shows a sign-in window for that account, once (step 7 there). After the
   sign-in, re-run the credential-fill creation, adding `username=USERNAME` as a third
   line of the `git credential fill` input so it selects that account's credential.
2. **gh.** `gh auth login` for that account (install gh first if needed — see the
   fallback list below), then `gh repo create REPO --private`.

If both fail, have the user create the repo at github.com/new (private, no README) and
continue with the push runbook. Whichever path you take, keep the chosen username in the
remote URL so the two accounts never mix.

**Create it with the cached credential** (no new sign-in, no gh needed) — run through
Git Bash like every other bash snippet here. **Don't fight quoting:** on Windows,
passing this snippet inline through PowerShell (`bash -lc '...'`) mangles the `\n`
escapes and wastes turns. Instead, write the snippet to a temp `.sh` file OUTSIDE the
project (e.g. `$env:TEMP\substrait-mkrepo.sh`) with your file-write tool, run it with
Git Bash (`bash /path/to/substrait-mkrepo.sh`), and delete it afterwards. A `.sh` file
outside the project doesn't break the no-PowerShell-scripts rule — that rule is about
`.ps1` files and project files.

```bash
CRED=$(printf 'protocol=https\nhost=github.com\n\n' | git credential fill)
TOKEN=$(printf '%s' "$CRED" | sed -n 's/^password=//p')
LOGIN=$(printf '%s' "$CRED" | sed -n 's/^username=//p')
curl -sS -X POST https://api.github.com/user/repos \
  -H "Authorization: token $TOKEN" -H "Accept: application/vnd.github+json" \
  -d '{"name":"REPO","private":true}'
```

Rules for this flow:

- **Always `"private": true`.** App repos are private, in the user's personal account.
- **Never print, echo, or paste the token anywhere** — not in the conversation, not in a
  file, not in an error report. Use it and discard the variables.
- A **401/403 or an empty token** means the cached credential can't create repos on this
  machine. Fall back in order: (1) `gh repo create REPO --private` — if gh isn't
  installed, install it yourself (`winget install --scope user GitHub.cli`, no admin
  needed) and sign in with `gh auth login` (device-code flow: relay the code and URL to
  the user as text, same rules as the Substrait link flow); (2) only if gh also fails,
  walk the user through creating it at github.com/new (private, no README) — the one
  case where they open GitHub.
- A **422 "name already exists"** means the repo is already there — skip creation and
  continue to the push runbook.

Then push using `docs/github-pushing.md` (username-in-remote, `main` branch).
