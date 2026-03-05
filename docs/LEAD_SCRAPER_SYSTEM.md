# Lead Scraper System Documentation

## 1. Purpose

This system is a zero-cost contact-intelligence pipeline focused on:

1. Finding business-usable emails first
2. Falling back to quality social handles when email is unavailable

Primary implementation spec:

- `docs/CONTACT_INTELLIGENCE_SPEC.md`

Optimization notes:

- `docs/EFFICIENCY_NOTES.md`

## 2. End-to-End Flow

1. Configure discovery and extraction in the Next.js UI.
2. `POST /api/leads/discover` runs `lead-scraper/discovery/discover.py`.
3. Discovery outputs `targets.txt` and `targets.csv`.
4. `POST /api/leads/extract` runs `lead-scraper/crawler/extract_contacts.py`.
5. Extractor writes `results.jsonl`, `results.csv`, and `progress.json`.
6. UI polls:
7. `GET /api/leads/progress` for live run counters and tier metrics.
8. `GET /api/leads/status` for output file readiness/history.
9. `GET /api/leads/top` for filtered ranked leads.
10. User downloads CSV via `GET /api/leads/download`.

## 3. Architecture

## 3.1 UI Layer

File: `app/page.tsx`

Features:

- Discovery controls: source, DDG pages, CRT keyword, CRT limit, queries
- Extraction controls:
- workers
- max pages
- timeout
- min/max delay
- early-stop confidence score
- optional MX validation toggle
- Live extraction progress panel (processed, remaining, tier rates, retries)
- Top Leads panel with filters:
- platform
- status
- tier
- min score
- limit
- email-only toggle
- History table and CSV export buttons

## 3.2 API Layer

- `POST /api/leads/discover`
- `POST /api/leads/extract`
- `GET /api/leads/progress`
- `GET /api/leads/status`
- `GET /api/leads/top`
- `GET /api/leads/download?file=targets|results`

## 3.3 Script Runner Bridge

File: `lib/lead-scraper.ts`

Responsibilities:

- build CLI args for discovery/extraction
- spawn Python scripts
- capture stdout/stderr and exit code
- enforce long extractor runtime window

Key env var:

- `LEAD_SCRAPER_PYTHON`

## 3.4 Discovery Script

File: `lead-scraper/discovery/discover.py`

Implemented:

- DDG scraping with multi-selector parsing + fallback
- DDG redirect decoding (`uddg`)
- retry + backoff (`1s`, `2s`, `4s`)
- CRT discovery with retry handling
- URL normalization and dedupe
- TXT + CSV output

## 3.5 Extraction Script

File: `lead-scraper/crawler/extract_contacts.py`

Implemented extraction layers:

1. `mailto` parsing
2. visible regex extraction
3. JSON-LD email extraction
4. obfuscated email normalization and extraction
5. policy/legal page extraction priority
6. social fallback extraction (including Pinterest)

Implemented reliability logic:

- retries + backoff on page fetch
- max pages/domain
- per-domain early stop when confidence reaches threshold
- robots check at root
- domain-level error isolation

Implemented quality logic:

- email junk filtering (`noreply`, `example`, platform domains, etc.)
- domain-match preference in confidence scoring
- optional MX validation with local cache file
- tier classification (`tier_a`, `tier_b`, `tier_c`)

## 4. Data Outputs

## 4.1 Discovery Output (`targets.csv`)

Columns:

- `url`

## 4.2 Extraction Output (`results.csv`)

Columns:

- `domain`
- `url`
- `best_contact_type`
- `best_contact_value`
- `confidence_score`
- `email_primary`
- `email_all`
- `email_source`
- `email_valid_syntax`
- `email_valid_mx`
- `instagram`
- `facebook`
- `linkedin`
- `x`
- `tiktok`
- `pinterest`
- `platform`
- `status`
- `tier`
- `lead_score`
- `pages_scanned`
- `crawl_ms`
- `retries_used`
- `error`

## 4.3 Progress Output (`progress.json`)

Core fields:

- `running`
- `domains_total`
- `domains_processed`
- `remaining`
- `emails_found`
- `tier_a`, `tier_b`, `tier_c`
- `pct_tier_a`, `pct_tier_b`, `pct_tier_c`
- `avg_pages_scanned`
- `avg_seconds_per_domain`
- `retries_used_total`
- `updated_at`

## 5. Contact Intelligence Model

Goal hierarchy:

- Primary: email contact
- Secondary: social profile contact
- Fallback: metadata-only

Confidence model (implemented):

- `mailto`: 100
- `visible`: 90
- `policy`: 80
- `jsonld`: 70
- `obfuscated`: 60
- social fallback baseline: 40

Domain-match bonus is applied to email confidence.

## 6. Runtime Defaults (Recommended)

- discovery source: `crt` for baseline
- CRT limit: `300-1000` for tests
- workers: `3-5`
- pages/domain: `4-5`
- timeout: `15-20s`
- delay: `0.7-2.0s`
- early stop score: `95`
- MX validation: off by default (enable for quality pass)

## 7. Known Constraints

1. DDG may intermittently return low/no results due anti-bot behavior.
2. MX validation increases runtime and depends on DNS/network quality.
3. Some domains block scraping despite conservative settings.
4. Very large target sets require long execution windows.

## 8. Safety and Compliance

- Respect robots and site terms.
- Keep request rates conservative.
- Use contact data under applicable outreach/privacy laws.

## 9. Developer Commands

Install Python deps:

```powershell
python -m pip install -r lead-scraper\requirements.txt
```

Run app:

```powershell
npm run dev
```

If Python path is not on PATH:

```powershell
$env:LEAD_SCRAPER_PYTHON="$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
npm run dev
```

Run scripts directly:

```powershell
python lead-scraper\discovery\discover.py --queries-file lead-scraper\data\queries.txt --source both --crt-limit 1000
python lead-scraper\crawler\extract_contacts.py --input lead-scraper\data\targets.txt --workers 5 --max-pages 5 --early-stop-score 95
```
