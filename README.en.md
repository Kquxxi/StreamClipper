# StreamClipper

## Environment Setup (.env)

1. Copy `.env.example` to `.env`.
2. Fill in secrets and settings for modules (Twitch, Kick, Publer, transcription).
3. Run the app: `python -u app\main.py` (the app automatically loads `.env`).

> Note: `.env` and `config.env` are ignored by Git. Code uses `load_dotenv()` with a fallback to `config.env`.

### Key Variables

- Twitch: `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET` (+ options: `TWITCH_WINDOW_HOURS`, `TWITCH_MIN_VIEWS`, `TWITCH_REQUEST_TIMEOUT`, `TWITCH_MAX_PAGES`, `TWITCH_MIN_FOLLOWERS`, `TWITCH_REPORT_MAX_STREAMERS`).
- Kick cookies (choose one):
  - From browser: `KICK_COOKIES_FROM_BROWSER` (e.g., `chrome`, `edge`, `firefox`, `brave`, `chromium`).
  - From file: `KICK_COOKIES_FILE` (Netscape cookie file path).
  - Optional header: `KICK_USER_AGENT`.
- Publer: `PUBLER_API_KEY`, `PUBLER_WORKSPACE_ID`, and `PUBLER_ACCOUNT_IDS` (comma separated) or `PUBLER_ACCOUNT_ID` (single).
- Transcription: `HF_TOKEN` (optional), `TRANSCRIBE_PYTHON`, `TRANSCRIBE_TIMEOUT_SEC`, `TRANSCRIBE_LANGUAGE`, `TRANSCRIBE_MODEL`, `TRANSCRIBE_DIAR`.
- Server: `PORT`, `HOST`, `DEBUG`, `ENABLE_SCHEDULER`.
- Paths/data: `DATA_DIR` (defaults to project root if empty). Additional: `TWITCH_DB_FILE`, `STREAMERS_DB_FILE`, `TWITCH_DATABASE_FILE`, `KICK_DATABASE_FILE`.

### Quick Start (Windows PowerShell)

```powershell
Copy-Item .env.example .env
# Edit .env and fill values
python -u app\main.py
```

Optional override `PORT/DEBUG` from shell:

```powershell
$env:PORT = "5001"; $env:DEBUG = "false"; python -u app\main.py
```

### Notes on Secrets & Sensitive Files

- Do not commit real secret values — use `.env`.
- Kick cookies are sensitive; `*cookies*.txt` patterns are ignored in `.gitignore`.
- Runtime caches/backups/reports are ignored via `.gitignore`.

## Endpoints

- UI: `GET /editor` – clip selection/editing and rendering interface.
- Health: `GET /health` – quick server status.

### Twitch Report
- `POST /api/update-streamers` – update streamers database (based on ENV).
- `POST /api/generate-raport` – generate Twitch report.
- `GET /raport`, `GET /api/report-status`, `GET /api/report-ready` – preview and status.

### Kick Report
- `GET /api/generate-raport-kick` – generate Kick report data.
- `GET /raport-kick`, `GET /api/report-kick-status`, `GET /api/report-kick-ready` – preview and status.

### Selection & Cache
- `POST /api/selection` – save selected clips.
- `POST /api/ensure-cache` – download clips + generate previews; `GET /api/ensure-cache/status` – status.
- `GET /media/previews/<name>`, `GET /media/clips/<name>`, `GET /media/exports/<name>`, `GET /media/subtitles/<name>` – serve files.

### Transcription / Render
- `POST /api/transcribe` – start transcription (WhisperX); `GET /api/transcribe/status` – status.
- `POST /api/crop` – set crop for a clip.
- `POST /api/render` – render video; `GET /api/render/status` – status.

### Publish (Publer)
- `POST /publish/<clip_id>` – upload + publish/schedule (dry‑run if keys missing).
- `GET /api/publer/workspaces`, `GET /api/publer/accounts`, `GET /api/publer/timeslots`, `GET /api/publer/available-slots`, `GET /api/publer/post-status` – Publer helper APIs.

### Internal Scheduler
- `POST /api/internal-scheduler/schedule` – internal post scheduling.
- `GET /api/internal-scheduler/posts` – list scheduled posts; `DELETE /api/internal-scheduler/posts/<post_id>` – delete.
- `POST /api/internal-scheduler/push-to-publer` (and variants with `clip_id`/`post_id`) – push to Publer.
- `GET /api/internal-scheduler/status`, `POST /api/internal-scheduler/start`, `POST /api/internal-scheduler/stop` – scheduler control.

## Run via Cloudflared

- Start tunnel:
  - `cloudflared tunnel run <name>`
  - or: `cloudflared tunnel --config C:\\ProgramData\\Cloudflare\\config.yml run`
- Find public tunnel URL in Cloudflare Dashboard and copy the `Cloudflare URL`/`Hostname`.
- Set `PUBLIC_BASE_URL` in `.env` (no trailing slash):
  - `PUBLIC_BASE_URL=https://your-tunnel.example`
- Run the app: `python -u app\main.py`.

Tips:
- If dev server runs on `http://127.0.0.1:5001`, make sure the tunnel maps to this port.
- `PUBLIC_BASE_URL` is used to generate public links and integrate publishing; it’s not required for publishing the repo to GitHub.
- Do not commit Cloudflared config files or tunnel secrets.

## Generated Files & Cache

- `scheduled_posts.json` (and `scheduled_posts.json.backup_*`) – local publishing queue; created automatically by the internal scheduler or when scheduling a post.
- `selection.json` – local user’s selected clips; we provide `selection.example.json` with an empty structure.
- `reports/**`, `raport.html`, `raport_data.json`, `kick/raport_kick.html`, `kick/raport_kick_data.json` – report outputs; ignored.
- `kick/kick_clips_cache*.json`, `kick/progress.json` – Kick caches and progress; ignored.
- `media/clips/**`, `media/exports/**`, `media/previews/**`, `media/subtitles/**` – large media/render outputs; ignored.
- `transcribe/*.json`, `transcribe/*.srt` – transcription outputs; ignored.
- `locks/` – scheduler lock files; ignored.
- `*.tmp`, `*TEMP_MPY*` – temporary files (e.g., MoviePy); ignored.

## License

- No license chosen. Default is “all rights reserved”: others can view but cannot legally use, modify or redistribute your code.
- If you want to allow usage (open-source), consider adding a license (e.g., MIT or Apache‑2.0). This can be added later when you decide.
