# Efficiency Notes

This file captures build ideas that improve contact yield and runtime efficiency without paid services.

## 1. Priority Scheduler by Domain

- Keep a per-domain queue with weighted priorities:
- homepage -> highest
- policy/contact pages -> medium
- generic discovered links -> low
- Benefit: higher email hit-rate early, fewer wasted requests.

## 2. Adaptive Early Stop

- Current early stop uses a static confidence threshold.
- Better: dynamic threshold by page budget left.
- Example: if score >= 90 and only 1 page left, stop immediately.

## 3. DNS/MX Cache Persistence

- MX cache already exists.
- Improvement: TTL metadata per domain to avoid stale records.
- Benefit: faster repeat runs and fewer DNS calls.

## 4. Domain Batch Sampling Mode

- Add runtime option to process first `N` targets or random sample.
- Benefit: quick test cycles before full scans.

## 5. Smart Retry Budget

- Track retries per domain and stop after global retry budget.
- Benefit: prevents heavy time loss on protected/broken sites.

## 6. Response Fingerprint Deduplication

- Hash normalized HTML to detect duplicate pages across URLs on same domain.
- Benefit: skip redundant parsing work.

## 7. Incremental Runs

- Store `last_processed_at` and `last_contact_score` per domain.
- Re-crawl low-confidence/no-contact domains more frequently.
- Skip recently high-confidence domains.

## 8. Output Partitioning

- Save separate CSVs per tier:
- `tier_a_emails.csv`
- `tier_b_social_only.csv`
- `tier_c_no_contact.csv`
- Benefit: faster downstream workflows.

## 9. UI Performance

- For large result sets, fetch top leads with cursor pagination.
- Benefit: avoids loading large payloads in single request.

## 10. Observability Upgrades

- Add run-level `contact_yield_per_minute` and `domains_per_minute`.
- Benefit: quickly compare tuning profiles (workers, delays, timeout).
