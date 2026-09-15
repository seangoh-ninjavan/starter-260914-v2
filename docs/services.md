# Adding Redis, Kafka, vector search or file storage

Declaring it in `substrait.yaml` is the **only** trigger. Installing a client library does
nothing — the service won't exist and the app will crash at runtime with no build warning.

```yaml
services:
  object-storage: {}     # → OBJECT_STORAGE_BUCKET (private GCS bucket, one per environment)
  redis: {}              # → REDIS_URL=redis://redis:6379/0
  kafka:                 # → KAFKA_BROKERS=kafka:9092 (single-node Redpanda, Kafka-compatible)
    persistent: true
  qdrant: {}             # → QDRANT_URL=http://qdrant:6333 (gRPC on qdrant:6334)
```

**For file uploads use `object-storage`.** Files written to the container filesystem are
lost on every restart and redeploy. See `docs/object-storage.md` for the full guide.

## Pod services vs object-storage

**Redis, Kafka and Qdrant** are pod services — containers running in the app's namespace.

- **Ephemeral by default.** Data is lost on pod restart. Treat redis as a cache; recreate
  qdrant collections if missing at startup.
- **`persistent: true`** adds a disk that survives restarts and redeploys (redis 1Gi, kafka
  10Gi, qdrant 5Gi). Only applies to these three pod services.
- Removing a pod service from the manifest removes it on the next deploy. The disk is kept;
  re-declaring re-adopts it.
- Pod services are reachable **only from inside the app's own namespace**.
- The kafka broker trades strict fsync durability for footprint — use it for events and jobs,
  not as a system of record.

**`object-storage` is NOT a pod** — it is a private cloud bucket. It differs on every axis:
it takes no options (no `persistent`), holds durable data by default, is reached over the
network with a GCS client, and needs **no credential**. See `docs/object-storage.md`.

## Important rules

- A service the app **already uses MUST stay declared** — omitting it removes the service on
  the next deploy.
- The catalogue is exactly these four (`object-storage`, `redis`, `kafka`, `qdrant`). Anything
  else fails validation at deploy with the fix in the message.
- Never list `REDIS_URL`, `KAFKA_BROKERS`, `QDRANT_URL` or `OBJECT_STORAGE_BUCKET` in
  `.env.example` — the platform injects them and the server rejects those names.
