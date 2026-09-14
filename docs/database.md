# Adding a database

Declare it in `substrait.yaml`, or nothing is provisioned:

```yaml
database: oceanbase   # shared HA cluster, MySQL wire protocol, backed up — the default
# database: postgres  # or mysql — the app's OWN single-node pod, 10Gi, no HA, no backups
```

**The engine cannot be changed once deployed** — changing this value fails the deploy.
Choose deliberately the first time.

With `oceanbase` you are writing **MySQL**, not PostgreSQL: no `SERIAL`, no `RETURNING`, no
`ILIKE`, no `$1` placeholders. Use `BIGINT AUTO_INCREMENT`, `%s` placeholders. Never
substitute SQLite, not even for local testing — different driver, different placeholders,
different dialect.

**NEVER use Python `%` string formatting or f-strings to build SQL queries.** Always use
parameterized queries — `cursor.execute("... %s ...", (value,))`. This avoids SQL injection
AND prevents format-character clashes (e.g. `%Y` in a date format being misread as a Python
format specifier, which crashes the app with `unsupported format character`).

**The driver is pinned — do not choose one freely.** Async database code (SQLAlchemy
asyncio): `asyncmy==0.2.14`, exactly — never an older pin (0.2.9 has no wheel for the
Dockerfile's Python 3.12, so the deploy build fails at pip). Sync database code:
`PyMySQL` plus `cryptography`. General rule for ANY package you add: deploys build with
`--only-binary=:all:` on Python 3.12 and can never compile from source, so a compiled
package must ship a prebuilt cp312 wheel — check PyPI before pinning if you are not
certain.

**Parse `DATABASE_URL` with percent-decoding.** The injected URL percent-encodes special
characters in the username and the password (e.g. `%40` for `@`). Parse it with a real URL
parser and `unquote` BOTH the username and the password — a hand-rolled split fails at
runtime with "Access denied", which looks like a platform problem and isn't. While you're
there: give the app an exception handler that returns a readable error message instead of a
blank 500, so runtime failures can be diagnosed from the page.

**Two DDL shapes wedge the app permanently. Both are rejected at validation, and if one
ever lands it leaves a failed row in Flyway history that makes *every later deploy* fail:**

- Never add a column and its foreign key in one `ALTER TABLE` — split into two statements.
- Never use a self-referencing foreign key with `ON DELETE CASCADE`.

If a migration has already failed, fixing the SQL is not enough: the user must go to the
portal → the app's **Database** tab → **Repair migration history** first.

## No database connected? Use temporary memory

Every app you build MUST also run on a machine with no `DATABASE_URL` — that is how the
user tests locally before deploying (there is no local database and never will be; never
substitute SQLite).

- At startup, check for `DATABASE_URL`. Present → use the real database as normal.
  Absent → use a plain in-process store (dicts/lists) behind the SAME data-access
  functions, so every feature works identically.
- Make the mode visible: when running on temporary memory, log it at startup and show a
  small notice in the page (e.g. "Local test mode — data is not saved").
- Never write "temporary" data to files as a workaround, and never skip features in
  local mode — the point is that the user can try everything before it goes live.
- **The database driver must never block a local run.** Import it only where a real
  `DATABASE_URL` is used (create the engine lazily), so the app starts without it. If the
  driver fails to pip-install on the user's machine — typically no prebuilt wheel for
  their Python version, "needs build tools" — do NOT debug it, do NOT switch drivers,
  and do NOT change the pin: skip that package locally, run on temporary memory, and
  tell the user in one sentence that this is normal and the deployed app is unaffected
  (the deploy installs it inside Docker, where the pinned version is guaranteed to work).

## Where logging goes

**All logging goes to stdout** — `print` or Python's `logging` to the console — **never to
a file.** The container's filesystem is wiped on every restart and redeploy, and nothing
can read a file inside it, so a log file is silently useless.

Know where stdout is actually visible: **locally**, live in the dev-server window while
the user tests — that is where logging earns its keep. **Deployed, it is NOT visible**:
the portal has no logs view (verified — the app page has no Logs tab), so never tell the
user to "check the logs" on a live app. This makes readable error responses mandatory,
not optional (see the `DATABASE_URL` note above): when something fails at the live URL,
the page itself must say what went wrong in plain language, because the page is the only
surface anyone can see. Diagnose live problems by reproducing them locally, where the
logs exist.
