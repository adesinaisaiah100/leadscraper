# Ecomscrape

Zero-cost e-commerce lead discovery and contact extraction with a Next.js control panel and Python scraping engine.

## What You Built

- A web dashboard to run discovery and extraction from the browser
- Discovery via:
- DuckDuckGo static HTML dorks
- `crt.sh` certificate transparency logs (`myshopify.com` footprint)
- Contact extraction crawler that gathers:
- Emails
- Social handles (Instagram, Facebook, LinkedIn, X/Twitter, TikTok)
- CSV + JSONL exports for downstream use
- Run history table showing file status, counts, size, and last run time
- Live extraction progress (processed, remaining, emails found)

## Architecture

- Frontend: Next.js App Router UI (`app/page.tsx`)
- Backend API routes:
- `POST /api/leads/discover`
- `POST /api/leads/extract`
- `GET /api/leads/status`
- `GET /api/leads/progress`
- `GET /api/leads/download?file=targets|results`
- Python scripts:
- `lead-scraper/discovery/discover.py`
- `lead-scraper/crawler/extract_contacts.py`
- Node/Python bridge:
- `lib/lead-scraper.ts`

## Requirements

- Node.js 20+
- npm 10+
- Python 3.11+ (3.12 recommended)

## Setup

### 1. Install Node dependencies

```powershell
npm install
```

### 2. Install Python dependencies

```powershell
python -m pip install -r lead-scraper\requirements.txt
```

If `python` is not on PATH, set this before running Next.js:

```powershell
$env:LEAD_SCRAPER_PYTHON="$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
```

## Run the App

```powershell
npm run dev
```

Open `http://localhost:3000`.

## How to Use

### Discovery

- Pick `Source`:
- `ddg`: dork discovery only
- `crt`: certificate discovery only
- `both`: combines both
- Set `Pages per Query` (DDG)
- Set `CRT Keyword` (optional; usually leave blank unless filtering by subdomain text)
- Set `CRT Limit` (start low for testing, e.g. 300–1000)
- Enter queries (one per line)
- Click `Start Discovery`

### Extraction

- Set `Workers` (start with 3–5)
- Set `Max Pages / Site` (start with 4–5)
- Click `Start Extraction`

### Export

- `Export Targets` downloads discovered targets CSV
- `Export Results` downloads extracted contacts CSV

## Output Files

- `lead-scraper/data/targets.txt`
- `lead-scraper/data/targets.csv`
- `lead-scraper/data/results.jsonl`
- `lead-scraper/data/results.csv`
- `lead-scraper/data/progress.json`

## API Reference

### `POST /api/leads/discover`

Request body:

```json
{
  "queries": ["inurl:myshopify.com"],
  "source": "both",
  "pages": 2,
  "delay": 2,
  "crtKeyword": "",
  "crtLimit": 1000
}
```

Response includes:

- `ok`, `code`, `command`
- `stdout`, `stderr`

### `POST /api/leads/extract`

Request body:

```json
{
  "workers": 5,
  "maxPages": 5
}
```

### `GET /api/leads/status`

Returns:

- readiness flags for targets/results
- history metadata (`count`, `sizeLabel`, `lastModified`)

### `GET /api/leads/progress`

Returns:

- current extraction run state (`running`)
- progress counters (`total`, `processed`, `remaining`)
- extraction counters (`emails_found`, `ok`, `no_contact`, `error`)

### `GET /api/leads/download?file=targets|results`

Downloads CSV file as attachment.

## DDG vs CRT Notes

- DDG can intermittently return zero due anti-bot responses or dork strictness.
- CRT is good for broad Shopify footprint discovery.
- `CRT Keyword` filters subdomain text; it is often too strict for generic words.

Practical strategy:

- Start with `source=crt`, empty `CRT Keyword`, moderate `CRT Limit`
- Run extraction on sampled targets
- Add DDG for niche targeting once baseline pipeline is stable

## Troubleshooting

### `pip` not recognized

Use:

```powershell
python -m pip install -r lead-scraper\requirements.txt
```

### WindowsApps `python.exe` alias issue

Disable app execution alias for `python.exe` and `python3.exe`, then use real Python path.

### Discovery fails with CRT timeout

Handled gracefully now. Retry with:

- `source=crt`
- lower `CRT Limit`
- stable network

### DDG returns zero

- test broad query: `inurl:myshopify.com`
- reduce strict quotes/operators
- set `pages=1` for first check

## Legal and Ethical Use

- Respect each site’s Terms and robots policy.
- Avoid aggressive concurrency.
- Use discovered contacts in compliance with applicable laws (e.g., CAN-SPAM/GDPR equivalents where relevant).

## Detailed Technical Documentation

See [docs/LEAD_SCRAPER_SYSTEM.md](docs/LEAD_SCRAPER_SYSTEM.md).
