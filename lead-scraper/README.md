# Lead Scraper Module

Python discovery and extraction engine used by the Next.js dashboard.

## Scripts

- `discovery/discover.py`: discovers target domains from DDG/CRT
- `crawler/extract_contacts.py`: crawls targets and extracts emails/socials
- `crawler/regex_utils.py`: shared extraction regex patterns

## Install

```powershell
python -m pip install -r lead-scraper\requirements.txt
```

## Discovery Examples

DDG only:

```powershell
python lead-scraper\discovery\discover.py --queries-file lead-scraper\data\queries.txt --source ddg --pages 2 --delay 2
```

CRT only (recommended baseline):

```powershell
python lead-scraper\discovery\discover.py --source crt --crt-limit 1000 --crt-keyword ""
```

Combined:

```powershell
python lead-scraper\discovery\discover.py --queries-file lead-scraper\data\queries.txt --source both --crt-limit 1000
```

Outputs:

- `lead-scraper/data/targets.txt`
- `lead-scraper/data/targets.csv`

## Extraction Example

```powershell
python lead-scraper\crawler\extract_contacts.py --input lead-scraper\data\targets.txt --workers 5 --max-pages 5
```

Outputs:

- `lead-scraper/data/results.jsonl`
- `lead-scraper/data/results.csv`
- `lead-scraper/data/progress.json` (live extraction progress)

## Stop + Clear (Dashboard)

Use the dashboard `Stop + Clear Extraction` action to:

- stop an active extraction run
- clear extraction outputs (`results.csv`, `results.jsonl`, `progress.json`)
- reset Top Leads/progress for a fresh discovery + extraction cycle

## Recommended Test Settings

- Discovery: `source=crt`, `crt-limit=300..1000`, `crt-keyword=` (empty)
- Extraction: `workers=3..5`, `max-pages=4..5`

## Notes

- `CRT keyword` filters subdomain text and can easily remove most results.
- DDG can intermittently produce zero results due anti-bot responses.
- Extractor checks `robots.txt` at domain root before crawling.
- Discovery and extraction use retry/backoff steps: `1s`, `2s`, `4s`.
- Results now include `domain`, `email_primary`, `email_all`, `platform`, `status`, and `lead_score`.

## Full Docs

See: `docs/LEAD_SCRAPER_SYSTEM.md` at repo root.
