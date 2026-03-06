# Lead Scraper Optimization Roadmap (Phase 1 to Phase 5)

## Goal

Upgrade the current lead scraper into a higher-quality, scalable contact-intelligence engine for general ecommerce stores (not Shopify-only), while keeping your existing Next.js + Python architecture and zero-budget tooling.

## Current Baseline (from your system docs)

- Discovery: DDG + CRT, URL dedupe, `targets.txt` and `targets.csv`
- Extraction: email/social extraction + scoring + progress tracking
- UI: controls for discovery/extraction, top leads filters, progress, reset

## Prerequisite Before Phase 1

- Restore `lead-scraper/crawler/extract_contacts.py` if missing/deleted.
- Confirm end-to-end baseline works:
1. run discovery
2. run extraction
3. view top leads
4. reset flow works

---

## Phase 1: Target Quality Scoring in Discovery

### Objective

Stop feeding low-quality domains into extraction by scoring discovered sites before crawl.

### What To Implement

1. Add a homepage validation pass in `lead-scraper/discovery/discover.py`.
2. For each discovered URL, fetch homepage once and compute `target_quality_score`.
3. Add detection signals:
- ecommerce platform signal (Shopify/WooCommerce/Magento/BigCommerce)
- ecommerce intent signal (`/products`, `cart`, `checkout`, `add to cart`)
- contactability signal (`/contact`, `mailto`, social links)
- health signal (status 200, non-parked, non-placeholder pages)
4. Add `quality_flags` and `platform_detected` fields.
5. Expand `targets.csv` columns from just `url` to:
- `url`
- `domain`
- `platform_detected`
- `target_quality_score`
- `quality_flags`
- `is_healthy`
6. Add API/UI option for minimum quality threshold (default: 50).

### Files To Change

- `lead-scraper/discovery/discover.py`
- `lib/lead-scraper.ts` (pass threshold flags)
- `app/api/leads/discover/route.ts`
- `app/page.tsx` (new control)
- `docs/LEAD_SCRAPER_SYSTEM.md`

### Acceptance Criteria

- Discovery output includes score and flags per target.
- Extraction runs only on targets above threshold.
- At least 20-40% reduction in dead/non-ecommerce domains in extraction input.

### Overall Benefit

Major quality lift with minimal architecture change. Extraction time is spent on likely real stores instead of noisy domains.

---

## Phase 2: Priority Crawl + Sitemap Expansion

### Objective

Increase email/social hit rate by crawling likely contact pages first and using sitemap discovery.

### What To Implement

1. In extractor, implement crawl order:
- homepage
- `/contact`, `/about`, `/support`, `/help`, `/team`, `/legal`, `/privacy`
2. Add sitemap support:
- fetch `/sitemap.xml`
- parse URLs
- prioritize contact/support/legal pages
3. Keep current early-stop behavior when high-confidence email found.
4. Track new metrics in progress/results:
- `priority_pages_scanned`
- `sitemap_urls_examined`
- `source_page_type` for best contact

### Files To Change

- `lead-scraper/crawler/extract_contacts.py`
- `app/api/leads/progress/route.ts` (if fields expanded)
- `docs/LEAD_SCRAPER_SYSTEM.md`

### Acceptance Criteria

- Extractor attempts sitemap when available.
- Priority pages are scanned before generic pages.
- Email discovery improves by measurable delta (target: +10% to +20%).

### Overall Benefit

High-impact extraction improvement at low cost; no paid APIs needed.

---

## Phase 3: Advanced Contact Signals (Obfuscation + Domain Guess + Social Email Pull)

### Objective

Recover contacts from sites that intentionally hide plain-text email.

### What To Implement

1. Expand obfuscation normalization:
- `[at]`, `(at)`, ` at ` -> `@`
- `[dot]`, `(dot)`, ` dot ` -> `.`
2. Add domain-based business email guesses:
- `info@`, `contact@`, `hello@`, `support@`, `sales@`
3. Validate guessed emails:
- syntax always
- optional MX check (existing toggle)
4. Social profile enrichment:
- if social links found, fetch profile page HTML and parse bio/about for email patterns
5. Add clear source labels:
- `obfuscated`
- `domain_guess`
- `social_profile`

### Files To Change

- `lead-scraper/crawler/extract_contacts.py`
- possibly `lead-scraper/crawler/regex_utils.py`
- `docs/LEAD_SCRAPER_SYSTEM.md`

### Acceptance Criteria

- New source types appear in `results.csv`.
- Guessed emails are scored lower than direct website emails.
- False-positive rate remains controlled via syntax/MX + junk filters.

### Overall Benefit

Improves coverage on modern stores where direct `mailto` is absent, while preserving quality ranking.

---

## Phase 4: Scoring, Ranking, and Dataset Quality Controls

### Objective

Make Top Leads reflect real outreach value by combining site quality + contact confidence.

### What To Implement

1. Split scoring model:
- `discovery_quality_score` (Phase 1 output)
- `contact_confidence_score` (current extraction confidence)
2. Create final `lead_score_v2`:
- weighted formula, e.g. `0.4 * discovery + 0.6 * contact`
3. Add quality gates:
- exclude parked/dead/spam-like domains
- downgrade generic or risky emails
4. Add UI filters:
- minimum discovery quality
- contact source type
- healthy-only toggle
5. Version score fields to avoid breaking old exports.

### Files To Change

- `lead-scraper/crawler/extract_contacts.py`
- `app/api/leads/top/route.ts`
- `app/page.tsx`
- `docs/LEAD_SCRAPER_SYSTEM.md`

### Acceptance Criteria

- Top leads visibly improve relevance.
- Filters allow separating high-intent business contacts from weak records.
- Score logic is documented and reproducible.

### Overall Benefit

Turns raw extraction into decision-ready lead intelligence with better precision in your top-ranked output.

---

## Phase 5: Scale and Reliability for Large Runs (100k to 1M Ready)

### Objective

Enable long-running, resumable, high-volume processing without rewriting your whole stack.

### What To Implement

1. Replace single-pass file workflow with queue state (SQLite first):
- `pending`, `processing`, `completed`, `failed`, `retry_count`
2. Batch extraction by chunks (e.g. 5k-20k targets per batch).
3. Add resumability:
- continue from last checkpoint after crash/restart
4. Add rate limiting policies:
- per-domain concurrency cap
- global worker cap
- retry budget by domain
5. Add operational telemetry:
- throughput (domains/min)
- success rate by source/platform
- fail reasons distribution
6. Optional: JS rendering fallback only for high-value failed domains to control compute cost.

### Files To Change

- `lead-scraper/crawler/extract_contacts.py` (queue integration)
- new queue helper module(s) under `lead-scraper/crawler/`
- `app/api/leads/progress/route.ts`
- `docs/LEAD_SCRAPER_SYSTEM.md`

### Acceptance Criteria

- Can stop/resume large runs without losing progress.
- Stable performance over long windows.
- Measured throughput and error observability available in UI/API.

### Overall Benefit

Makes the system production-tolerant for very large datasets while remaining zero-budget and maintainable.

---

## Recommended Implementation Order and Timeline

1. Phase 1 (highest ROI, low risk): 2-4 days
2. Phase 2 (major extraction lift): 3-5 days
3. Phase 3 (coverage expansion): 4-7 days
4. Phase 4 (quality ranking polish): 2-4 days
5. Phase 5 (scale hardening): 1-2 weeks

## KPI Targets Per Phase

- Phase 1: reduce low-quality targets by 20-40%
- Phase 2: improve email hit rate by +10% to +20%
- Phase 3: improve total contact coverage by +10% to +15%
- Phase 4: improve top-lead precision/acceptance by +20%+
- Phase 5: support stable large-run throughput with resumability

## Non-Goals (for focus)

- No paid APIs
- No full architecture rewrite
- No breaking existing CSV exports without versioning

## Final Outcome

After Phase 1-5, your app remains familiar but becomes:

- better at finding healthy ecommerce stores
- better at extracting quality public contacts
- better at ranking real opportunities
- capable of long, large-scale runs with operational control
