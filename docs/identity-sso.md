# Knowing who the user is

With Google SSO on, the platform injects `X-Forwarded-Email` and `X-Forwarded-User` headers
into every backend request. **Never build a login page, OAuth flow or session handling** —
just read the header:

```python
email = request.headers.get("X-Forwarded-Email")
```

The browser never sees these headers, so a frontend must ask a backend endpoint such as
`/api/me`. Headers are stripped on `/health` and on any public paths, and are spoofable if
SSO is off — so don't trust them for anything sensitive when SSO isn't enabled.
