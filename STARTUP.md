# Running Finance Guru locally

One-time setup (run once, in this folder, in your VS Code terminal):

```powershell
.\register-finance-guru.ps1
```

This adds a `finance-guru` command to your PowerShell profile. Restart your terminal after running it once.

From then on, from any terminal:

```powershell
finance-guru
```

This will:
- Start the backend (FastAPI) on `http://localhost:8000`
- Start the frontend (Next.js) on `http://localhost:6001`
- Open `http://localhost:6001` in your browser automatically

(Port 6001, not 6000 — Chrome and other Chromium browsers hard-block port 6000 specifically, since it's reserved for the X11 window system, and refuse to even attempt the connection. That's the `ERR_UNSAFE_PORT` error if you saw it — not an app problem. 6001 isn't on that blocked list.)

First run installs Python and npm dependencies (a few minutes); every run after that starts in a few seconds. Backend and frontend run in their own visible terminal windows — close those windows to stop the app, or just run `finance-guru` again later to restart it.

No Docker, Redis, or PostgreSQL needed for local use — this setup uses SQLite and an in-process job runner (see `backend/.env` for details, and how to switch to Redis/Postgres later if you want to).

If `finance-guru` isn't found after registering, you're likely in a different shell than PowerShell — open a PowerShell terminal specifically (VS Code: the dropdown next to the `+` in the terminal panel lets you pick "PowerShell").

You can also always run it directly without the alias:

```powershell
.\start-finance-guru.ps1
```
