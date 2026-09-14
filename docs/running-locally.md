# Running it locally — do this BEFORE every deploy

When the user says anything like *"run it on my computer so I can try it first"*, or after
any change worth checking, run the app locally and hand them the address. Treat local
testing as the default step before deploying, not an optional extra.

```bash
pip install -r backend/requirements.txt
cd backend && uvicorn main:app --reload --port 8000
```

- **If port 8000 is already in use, try the next port up** (8001, 8002, …) until you find
  a free one. Always tell the user which port the app is running on and give them the full
  clickable URL (`http://127.0.0.1:PORT`). Never silently fail with "address already in
  use" — just pick the next port.

- **The server runs until stopped, so it cannot live in this editor's runner** (the runner
  kills long waits — same reason as the link flow). Launch it in a window using the
  *Interactive steps* section in `docs/deploying.md`, or run it in the background if your
  runner supports that, then tell the user:

  > The app is running on your computer at **http://127.0.0.1:8000** — open that in your
  > browser and try it. Nobody else can see this address.

- Works with or without a database: locally there is no `DATABASE_URL`, so the app runs on
  temporary memory (see the *No database connected?* section in `docs/database.md`) —
  everything works, but records vanish when the server restarts. Say so if the app stores
  data:

  > On your computer the app uses temporary memory — anything you add here disappears
  > when it restarts. Once deployed, records are kept permanently in the database.

- When the user is happy, stop the server and proceed to commit → push → deploy.
- If Python is missing, don't fight it — deploy instead and read the live URL, but say
  that's what you're doing.

## Local object storage

If the app uses `object-storage`, add `fake-gcs-server` to your `docker-compose.yml`:

```yaml
fake-gcs:
  image: fsouza/fake-gcs-server
  ports:
    - "4443:4443"
  command: ["-scheme", "http", "-port", "4443"]
```

Then start it and run the backend with the emulator variable:

```bash
docker compose up -d fake-gcs
STORAGE_EMULATOR_HOST=http://localhost:4443 \
  cd backend && uvicorn main:app --reload --port 8000
```

The GCS client SDK (and the scaffold's `storage.py`) detects `STORAGE_EMULATOR_HOST`
automatically and routes all calls to the emulator. No other configuration needed.
