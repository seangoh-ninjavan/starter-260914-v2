# The API Library — building apps against existing APIs

The Substrait portal serves a catalogue of APIs an app can be built against. It has two kinds
of entries, and they are called in **two different ways** — getting them the wrong way round
is the mistake to avoid.

- **`internal`** — company APIs registered by platform admins. Each carries a name, slug,
  description, tags, a base URL, `auth_notes`, and a full OpenAPI spec. Apps call these
  **through the platform gateway**, never directly.
- **`app`** — deployed Substrait apps. Each has its endpoint inventory and its
  `https://<slug>.apps.substrait.build` URL. Apps call these **directly**.

## Browsing the library

```bash
bash substrait.sh library list [--q TERM] [--tag TAG]    # the whole catalogue (JSON)
bash substrait.sh library show internal|app SLUG         # one entry + endpoint summary
bash substrait.sh library spec [internal|app] SLUG [--out FILE]  # full OpenAPI doc
```

Needs the **account** personal access token (`sbt_…`) — an app-scoped deploy token cannot
browse the library. If you get a 401, run `bash substrait.sh link` first.

Prefer the endpoint summaries from `show`; pull a full spec to a file (`--out`) only when you
need request/response detail, and grep it rather than printing it.

**Data groups and visibility.** The catalogue is published through the org's data groups. An
operation (endpoint + method) is visible only to members who hold a group that names it. If
the catalogue comes back empty or an API is missing, suggest an org admin add the operations
to a data group the account holds — don't retry or treat it as an outage.

## Calling an internal API — through the gateway

Company APIs are never called with a credential the app holds. The app calls the platform's
**egress gateway**, and the gateway attaches the real credential on its behalf:

```
GET $SUBSTRAIT_EGRESS_URL/<entry-slug>/<the API's own path>
Authorization: Bearer $SUBSTRAIT_EGRESS_TOKEN
```

Both variables are injected by the platform. **Do not declare them in `.env.example`** — they
are reserved, and a declaration is *silently ignored* (the deploy succeeds but the variable
never appears, which is much harder to debug than an error).

**What this means for your design:**

- **Never design an env var for that API's key, token, or base URL.** There is nothing for
  the user to paste. If you find yourself writing `ORDERS_API_KEY=  # secret`, you have
  designed the pre-brokering shape by mistake.
- Build the URL from `$SUBSTRAIT_EGRESS_URL` + the entry slug + the path from the spec.
- `auth_notes` describes how the API authenticates — context for the design conversation, not
  instructions for the app to follow.

**Access must be granted before any call works.** The app needs an approved grant for that
entry, requested on the app's **Access** tab in the portal. Tell the user this is needed — an
app that builds fine and then 403s at the gateway looks like a bug when it is really a pending
approval. Raise it as part of shipping rather than leaving the user to discover it.

## Calling an app API — directly

Another Substrait app's API is **not** brokered. Call it directly at its
`https://<slug>.apps.substrait.build` base URL, which belongs in a custom env var in
`backend/.env.example` as it always did. Note it may sit behind that app's Google SSO proxy —
check with the app's owner whether a service path exists.

## Development access — seeing real responses while you build

A **person** (not an app) can be granted **development access** to call an internal API from
the editor through the platform:

```bash
bash substrait.sh library access                          # your access, every state
bash substrait.sh library request <slug> --reason "…"     # ask the data owner (≥10 chars)
bash substrait.sh library call <slug> GET /path           # make a real call
bash substrait.sh library call <slug> GET /path --out file.json  # save the response
```

What development access is:

- **Read-only.** `GET`, `HEAD` and `OPTIONS` only — writes are refused before they leave the
  platform.
- **Time-boxed.** The owner grants 30 or 60 days. When it lapses, `call` says so.
- **Scoped like the spec.** You can only call operations your account can *see*.
- **Production data.** Treat what comes back as you would production records — use it to learn
  shapes, never paste it into code, fixtures or commit messages.

Ask for it early — the owner is a person and may take a day — and keep designing from the spec
in the meantime. `show internal <slug>` carries `development_access` with your current state.

## Designing an app from the library

1. `list` the catalogue and shortlist entries relevant to what the user wants to build.
2. `show` the shortlisted entries; read `auth_notes` and the endpoint summaries.
3. Agree the design with the user: endpoints consumed, what the app stores vs fetches live,
   and the app's own API/frontend surface. Env vars only for `app` entries' base URLs —
   internal APIs need none.
4. Scaffold and implement, then link and deploy.
5. For each internal API consumed, make sure access is requested and approved — the app
   deploys without it and then gets refused at the gateway, so raise it as part of shipping.
