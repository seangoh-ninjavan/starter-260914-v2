# Object storage (file uploads)

Databases are the wrong home for bytes. Declare `object-storage` in `substrait.yaml` and
your app gets a **private bucket of its own** for uploads, generated documents, images and
exports.

## What you get

- **One private bucket per app**, injected as **`OBJECT_STORAGE_BUCKET`**.
- **No credential.** The pod authenticates as itself (Workload Identity). There is no key to
  mount, no secret to rotate, and **nothing about storage belongs in `.env.example`**. Never
  list `OBJECT_STORAGE_BUCKET` there — the platform injects it, and a declaration is silently
  ignored.
- **Time-limited signed URLs.** The app can mint short-lived URLs that let a browser download
  or upload straight into the bucket without the bytes passing through your pod — and without
  a credential in the link.
- **Isolation the platform enforces.** An app can reach its own bucket and no other. Buckets
  can never be made public: `make_public()` and ACL calls **fail** — that failure is the
  platform working, not a bug to route around.
- **Durable storage.** Files survive redeploys, rollbacks and manifest edits. Removing the
  `object-storage` declaration does NOT delete the bucket — the deploy just warns. The bucket
  is deleted only after the whole app is deleted, and after a grace period.

It is plain Google Cloud Storage, so **any language works** — use whatever GCS client your
stack has and let it pick up Application Default Credentials.

## Declare it

```yaml
# substrait.yaml
description: >
  Collects field-inspection photos and produces a signed-off PDF report per site visit.

services:
  object-storage: {}
```

That is the whole declaration — it takes **no options** (`persistent` applies only to the pod
services, and the bucket is durable regardless). `OBJECT_STORAGE_BUCKET` appears in the app's
environment on the next deploy.

## Reading and writing

The scaffold ships `backend/storage.py`, a small wrapper around the GCS SDK — eight public
functions:

| Function | What it does |
|---|---|
| `safe_key(part, ...)` | Build a safe key from parts — **mandatory** |
| `put_bytes(key, data, content_type)` | Upload bytes |
| `get_bytes(key)` | Download bytes |
| `exists(key)` | Check if a key exists |
| `delete(key)` | Delete (no-op if already gone) |
| `list_keys(prefix)` | List keys under a prefix |
| `download_url(key, expires_minutes)` | Signed download URL for browser |
| `upload_url(key, content_type, expires_minutes)` | Signed upload URL for browser |

```python
import storage

key = storage.safe_key(tenant_id, user_id, "report.pdf")
storage.put_bytes(key, pdf_bytes, content_type="application/pdf")

data    = storage.get_bytes(key)      # bytes
present = storage.exists(key)         # bool
keys    = storage.list_keys(f"{tenant_id}/")
storage.delete(key)                   # no-op if already gone
```

### `safe_key()` is mandatory

**Never use a client-supplied filename as a key.** A `/` inside it crosses into another
prefix and a name like `../other-tenant/secret.pdf` lands exactly where it says. Derive keys
yourself (`f"{tenant_id}/{user_id}/{uuid4()}"`), keep the original filename as your own
database column, and run every key through `safe_key()`.

It **raises `ValueError`** rather than sanitising — its charset is `A-Z a-z 0-9 . _ -` plus
`/` as the separator, up to 512 characters. A space, an accent, `+`, `%` or `#` is rejected.
Catch the `ValueError` and answer **400** wherever a client can influence what goes in, so a
name someone typed never becomes a 500.

An empty part is also an error — `safe_key(tenant_id, name)` with an empty `tenant_id` raises
rather than falling back to writing at the bucket root.

### Signed URLs for browser-direct transfer

For large files, skip the pod — let the browser talk to the bucket directly:

```python
# Give the browser a pre-signed upload URL
url = storage.upload_url(key, content_type="image/jpeg", expires_minutes=15)
# → return this to the frontend, which PUTs the file straight into the bucket

# Give the browser a pre-signed download URL
url = storage.download_url(key, expires_minutes=60)
# → return this to the frontend, which opens or fetches the file directly
```

No credential appears in the URL — it is signed by the pod's own identity.

## Local development

Use `fake-gcs-server` in Docker to emulate GCS locally:

```yaml
# Add to docker-compose.yml
fake-gcs:
  image: fsouza/fake-gcs-server
  ports:
    - "4443:4443"
  command: ["-scheme", "http", "-port", "4443"]
```

Then run with:

```bash
STORAGE_EMULATOR_HOST=http://localhost:4443 \
  uvicorn main:app --reload --port 8000
```

The GCS client SDK (and therefore `storage.py`) detects `STORAGE_EMULATOR_HOST` automatically
and routes all calls to the emulator. No other configuration needed.
