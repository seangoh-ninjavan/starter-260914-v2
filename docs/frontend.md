# If you add a frontend later

Only when the user asks. Then: `cicd/Dockerfile.frontend` serving the built site on **port
80**; call the backend same-origin via relative `/api` paths; **never hardcode an API URL
and never set `VITE_API_URL`**. Public build-time values go in a committed
`frontend/.env.production` (already un-ignored in `.gitignore`).
