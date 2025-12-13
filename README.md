# e2eClipUploader

## Opis aplikacji

- End‑to‑end narzędzie do pobierania, selekcji, transkrypcji, kadrowania (crop), renderowania i publikacji krótkich klipów z Twitch i Kick.
- Udostępnia interfejs webowy (`/editor`) do pracy z klipami oraz rozbudowane API do raportów i automatyzacji.
- Generuje raporty popularnych klipów/streamerów (Twitch/Kick), pozwala oznaczać preferencje streamerów i filtrować wyniki.
- Integruje się z Publer (API) w celu publikacji/schedulingu postów, dodatkowo posiada wewnętrzny lokalny scheduler, który utrzymuje kolejkę w plikach JSON.
- Przechowuje dane użytkownika i artefakty render/transkrypcji lokalnie (JSON + `media/**`), a repozytorium ignoruje je zgodnie z `.gitignore`.

## Architektura i przepływ działania

- Pobieranie danych: skrypty i endpointy zbierają klipy/streamerów (Twitch przez `twitchAPI`, Kick przez `KickApi`/scraper z cookies) i zapisują wyniki do lokalnych plików.
- Raportowanie: generatory raportów (Twitch/Kick) produkują dane i HTML‑fragmenty do podglądu; UI wyświetla jednolite tabele z filtrowaniem/prezentacją.
- Selekcja i cache: przez `/editor` wybierasz klipy; `/api/ensure-cache` pobiera pliki i tworzy prewki (z użyciem `yt-dlp` i `imageio-ffmpeg`).
- Transkrypcja i crop: `/api/transcribe` uruchamia pipeline (WhisperX przez adapter w `pipeline/transcribe`), `/api/crop` zapisuje parametry kadrowania.
- Render: `/api/render` tworzy eksport wideo (parametry z JSON); pliki wynikowe trafiają do `media/exports/**`.
- Publikacja: `/publish/<clip_id>` pakuje metadane i media, komunikuje się z Publer; wewnętrzny scheduler utrzymuje kolejkę w `scheduled_posts.json`.

## Narzędzia i technologie

- `Python` (aplikacja serwerowa i skrypty pomocnicze).
- `Flask` (serwer HTTP i UI), `Jinja2` (szablony HTML przez Flask/generator raportów).
- `requests`, `twitchAPI`, `KickApi` (integracje zewnętrzne), `python-dotenv` (konfiguracja przez `.env`).
- `APScheduler` / `schedule` (zadania cykliczne, wewnętrzny scheduler publikacji).
- `yt-dlp`, `imageio-ffmpeg` (pobieranie mediów, generowanie prewek), opcjonalnie ślady `MoviePy` (tymczasowe `*TEMP_MPY*`).
- `Cloudflared` (opcjonalne wystawienie lokalnego serwera na publiczny URL).

## Funkcje kluczowe

- UI edycji/wyboru klipów (`/editor`) z podglądem i zapisem selekcji (`selection.json`).
- Raporty Twitch/Kick z filtrowaniem i preferencjami streamerów (`streamers_prefs.json`).
- Transkrypcja (WhisperX) i ustawienia crop dla eksportów pionowych.
- Renderowanie wideo i serwowanie plików (previews/exports/subtitles).
- Harmonogram publikacji: lokalna kolejka (`scheduled_posts.json`) + integracja Publer API.
- API pomocnicze do pobrania cache, statusów zadań oraz zarządzania schedulerem.

## Konfiguracja środowiska (.env)

1. Skopiuj plik `.env.example` do `.env`.
2. Uzupełnij sekrety i ustawienia wymagane przez moduły (Twitch, Kick, Publer, transkrypcja).
3. Uruchom aplikację: `python -u app\main.py` (aplikacja automatycznie wczytuje `.env`).

> Uwaga: pliki `.env` i `config.env` są ignorowane przez Git (bezpieczne do lokalnego użycia). W kodzie stosowane jest `load_dotenv()` z fallbackiem do `config.env`.

### Kluczowe zmienne

- Twitch: `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET` (+ opcje okna i limitów: `TWITCH_WINDOW_HOURS`, `TWITCH_MIN_VIEWS`, `TWITCH_REQUEST_TIMEOUT`, `TWITCH_MAX_PAGES`, `TWITCH_MIN_FOLLOWERS`, `TWITCH_REPORT_MAX_STREAMERS`).
- Kick: wybierz jedną metodę cookies:
  - Z przeglądarki: `KICK_COOKIES_FROM_BROWSER` (np. `chrome`, `edge`, `firefox`, `brave`, `chromium`).
  - Z pliku: `KICK_COOKIES_FILE` (ścieżka do pliku cookies w formacie Netscape).
  - Opcjonalnie: `KICK_USER_AGENT` dla niestandardowego UA.
- Publer (publikacja): `PUBLER_API_KEY`, `PUBLER_WORKSPACE_ID`, oraz `PUBLER_ACCOUNT_IDS` (lista rozdzielona przecinkami) lub `PUBLER_ACCOUNT_ID` (pojedyncze konto).
- Transkrypcja: `HF_TOKEN` (opcjonalnie), `TRANSCRIBE_PYTHON`, `TRANSCRIBE_TIMEOUT_SEC`, `TRANSCRIBE_LANGUAGE`, `TRANSCRIBE_MODEL`, `TRANSCRIBE_DIAR`.
- Serwer: `PORT`, `HOST`, `DEBUG`, `ENABLE_SCHEDULER`.
- Ścieżki/dane: `DATA_DIR` (jeśli puste, użyty zostanie katalog projektu). Dodatkowe: `TWITCH_DB_FILE`, `STREAMERS_DB_FILE`, `TWITCH_DATABASE_FILE`, `KICK_DATABASE_FILE`.

### Szybki start (Windows PowerShell)

```powershell
Copy-Item .env.example .env
# Edytuj .env i uzupełnij wartości
python -u app\main.py
```

Opcjonalne nadpisanie `PORT/DEBUG` z powłoki:

```powershell
$env:PORT = "5001"; $env:DEBUG = "false"; python -u app\main.py
```

### Uwaga o sekretach i plikach wrażliwych

- Nie commituj realnych wartości sekretów do repozytorium – używaj `.env`.
- Cookies Kick są traktowane jako wrażliwe; wzorce `*cookies*.txt` są ignorowane przez `.gitignore`.
- Pliki cache/backup/raporty generowane w runtime są ignorowane zgodnie z `.gitignore`.

## Endpoints

- UI: `GET /editor` – interfejs do wyboru/edycji klipów i renderowania.
- Zdrowie: `GET /health` – szybki check działania serwera.

### Twitch Raport
- `POST /api/update-streamers` – aktualizacja bazy streamerów (wg ENV).
- `POST /api/generate-raport` – generacja raportu Twitch.
- `GET /raport`, `GET /api/report-status`, `GET /api/report-ready` – podgląd i status raportu.

### Kick Raport
- `GET /api/generate-raport-kick` – generacja danych raportu Kick.
- `GET /raport-kick`, `GET /api/report-kick-status`, `GET /api/report-kick-ready` – podgląd i status.

### Selekcja i cache
- `POST /api/selection` – zapis wybranych klipów.
- `POST /api/ensure-cache` – pobranie klipów + generacja prewki; `GET /api/ensure-cache/status` – status.
- `GET /media/previews/<name>`, `GET /media/clips/<name>`, `GET /media/exports/<name>`, `GET /media/subtitles/<name>` – serwowanie plików.

### Transkrypcja / Render
- `POST /api/transcribe` – uruchom transkrypcję (WhisperX); `GET /api/transcribe/status` – status.
- `POST /api/crop` – ustawienia crop dla klipu.
- `POST /api/render` – render wideo; `GET /api/render/status` – status.

### Publikacja (Publer)
- `POST /publish/<clip_id>` – upload + publish/schedule (dry‑run jeśli brak kluczy).
- `GET /api/publer/workspaces`, `GET /api/publer/accounts`, `GET /api/publer/timeslots`, `GET /api/publer/available-slots`, `GET /api/publer/post-status` – pomocnicze API Publera.

### Wewnętrzny scheduler
- `POST /api/internal-scheduler/schedule` – wewnętrzne planowanie postów.
- `GET /api/internal-scheduler/posts` – lista zaplanowanych postów, `DELETE /api/internal-scheduler/posts/<post_id>` – usunięcie.
- `POST /api/internal-scheduler/push-to-publer` (oraz warianty z `clip_id`/`post_id`) – wypchnięcie do Publera.
- `GET /api/internal-scheduler/status`, `POST /api/internal-scheduler/start`, `POST /api/internal-scheduler/stop` – kontrola schedulera.

## Uruchom przez Cloudflared

- Uruchom tunel:
  - `cloudflared tunnel run <name>`
  - lub: `cloudflared tunnel --config C:\ProgramData\Cloudflare\config.yml run`
- Znajdź publiczny URL tunelu w Cloudflare Dashboard (Zero Trust → Tunnels → Twój tunel) i skopiuj `Cloudflare URL`/`Hostname`.
- Ustaw w `.env` wartość `PUBLIC_BASE_URL`:
  - `PUBLIC_BASE_URL=https://twoj-tunel.example` (bez końcowego `/`).
- Uruchom aplikację: `python -u app\main.py`.

Wskazówki:
- Jeśli dev‑server działa na `http://127.0.0.1:5001`, upewnij się, że tunel mapuje ruch na ten port.
- `PUBLIC_BASE_URL` służy do generowania publicznych linków (previews/exports) i integracji publikacji; nie jest wymagany dla samej publikacji repo na GitHub.
- Nie commituj plików konfiguracyjnych Cloudflared ani sekretów tunelu.

## Pliki generowane i cache

- `scheduled_posts.json` (i `scheduled_posts.json.backup_*`) – lokalna kolejka publikacji; tworzona automatycznie przez wewnętrzny scheduler lub przy planowaniu posta.
- `selection.json` – lokalna lista wybranych klipów użytkownika; dostarczamy `selection.example.json` z pustą strukturą.
- `reports/**`, `raport.html`, `raport_data.json`, `kick/raport_kick.html`, `kick/raport_kick_data.json` – produkty generatorów raportów; ignorowane.
- `kick/kick_clips_cache*.json`, `kick/progress.json` – cache i postęp zadań Kick; ignorowane.
- `media/clips/**`, `media/exports/**`, `media/previews/**`, `media/subtitles/**` – duże pliki mediów i renderów; ignorowane.
- `transcribe/*.json`, `transcribe/*.srt` – wyniki transkrypcji; ignorowane.
- `locks/` – pliki blokad schedulera; ignorowane.
- `*.tmp`, `*TEMP_MPY*` – pliki tymczasowe (np. MoviePy); ignorowane.
