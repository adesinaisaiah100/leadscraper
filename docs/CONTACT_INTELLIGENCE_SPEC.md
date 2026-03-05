# Contact Intelligence Spec (Zero-Cost)

## 1. Objective

Build a reliable contact-intelligence pipeline that prioritizes **email discovery first** and gracefully falls back to **social handles** when email is unavailable.

Primary success condition per domain:

1. Business-usable email found and scored
2. If no usable email, at least one high-quality social account found

## 2. Design Principles

- Prioritize **contact yield per domain-second**.
- Keep stack zero-cost: `requests`, `BeautifulSoup`, local files, optional local DNS checks.
- Limit crawling breadth; maximize page quality.
- Stop early when a high-confidence email is found.
- Produce auditable outputs: source, confidence, and status for each lead.

## 3. Success Tiers

- `Tier A`: valid business email found
- `Tier B`: no email, but one or more quality social handles found
- `Tier C`: no usable contact

Target KPI baseline:

- Tier A + Tier B should be materially higher than current baseline
- Track trend over runs, not single-run spikes

## 4. Crawl Strategy

## 4.1 Page Priority Order

1. `/`
2. `/contact`
3. `/pages/contact`
4. `/about`
5. `/pages/about`
6. `/support`
7. `/help`
8. `/legal`
9. `/terms`
10. `/privacy`
11. `/policies/privacy-policy`
12. `/policies/contact-information`

## 4.2 Crawl Limits

- Default pages/domain: `5`
- Maximum pages/domain: `6`
- Worker range: `3-5` default
- Early stop: stop crawling additional pages once high-confidence email threshold is met

## 5. Extraction Layers (Priority Pipeline)

Order to execute per page/domain:

1. `mailto:` extraction from anchor tags
2. Visible text regex email extraction
3. JSON-LD / structured metadata email extraction
4. Obfuscated email normalization + regex extraction
5. Policy/legal page extraction
6. Social profile extraction (fallback)

## 5.1 Layer Details

### Layer 1: Mailto

- Parse all `a[href]`
- If `href` starts with `mailto:`, extract and normalize
- Mark source as `mailto`

### Layer 2: Visible Regex

- Apply email regex to HTML text and selected attributes
- Mark source as `visible`

### Layer 3: JSON-LD

- Parse `script[type="application/ld+json"]`
- Extract `email` fields recursively when present
- Mark source as `jsonld`

### Layer 4: Obfuscated

Normalize before regex:

- `[at]`, `(at)`, ` at ` -> `@`
- `[dot]`, `(dot)`, ` dot ` -> `.`

Mark source as `obfuscated`.

### Layer 5: Policy / Legal

- Explicitly scan policy endpoints in priority list
- Mark source as `policy` when originating from policy/legal pages

### Layer 6: Social Fallback

Extract:

- Instagram
- Facebook
- LinkedIn
- Twitter/X
- TikTok
- Pinterest

If no usable email, socials become primary contact channel.

## 6. Email Quality Rules

Reject if local part contains:

- `noreply`
- `no-reply`
- `donotreply`
- `example`
- `test`

Reject if domain is in blocklist:

- `shopify.com`
- `example.com`
- `test.com`

Preference rules:

- Prefer email domain matching site root domain or subdomain
- Keep non-matching emails as secondary candidates, not primary

## 7. Validation

Required:

- Syntax validation (regex + sanity checks)

Optional (toggle):

- MX check per domain
- Cache MX results locally to avoid repeated DNS lookups

## 8. Contact Confidence Scoring

Base scoring model:

- `mailto`: `100`
- visible email: `90`
- policy page email: `80`
- JSON-LD email: `70`
- obfuscated email: `60`
- social-only contact: `40`

Tie-breakers:

- +10 if email domain matches site domain/subdomain
- -20 if weak/junk pattern matched (if not fully rejected)

Output fields:

- `best_contact_type`
- `best_contact_value`
- `confidence_score`

## 9. Output Schema (Target)

Per-domain result fields:

- `domain`
- `url`
- `best_contact_type`
- `best_contact_value`
- `confidence_score`
- `email_primary`
- `email_all`
- `email_source`
- `email_valid_syntax`
- `email_valid_mx` (nullable / optional)
- `instagram`
- `facebook`
- `linkedin`
- `x`
- `tiktok`
- `pinterest`
- `platform`
- `status` (`ok`, `no_contact`, `error`)
- `lead_score`
- `pages_scanned`
- `crawl_ms`
- `error`

## 10. Runtime Metrics (Per Run)

Track and expose:

- `domains_total`
- `domains_processed`
- `% tier_a_email`
- `% tier_b_social_only`
- `% tier_c_no_contact`
- `emails_found_total`
- `avg_pages_scanned`
- `avg_seconds_per_domain`
- `error_rate`
- `retries_used_total`

## 11. Failure Handling

- Timeouts: retry with backoff (`1s`, `2s`, `4s`)
- 403/blocked: mark domain `error` and continue
- unreachable domain: mark and continue
- malformed HTML/JSON-LD: skip parsing error, continue
- no email found: return socials if present

Pipeline should never fail whole-run because of single-domain issues.

## 12. Performance Guardrails

- Keep request concurrency moderate (`3-5` default)
- Keep max pages/domain low (`5` default)
- Early stop on high-confidence email
- Deduplicate domains and contacts aggressively

## 13. Zero-Cost Constraints

Must remain free:

- No paid APIs required
- No paid proxy dependency
- Local file outputs (`csv/jsonl/json`)
- Optional DNS checks only if local/network permits

## 14. Phased Implementation Plan

## Phase 1 (Core Reliability)

- Add missing extraction layers (mailto/jsonld/obfuscation)
- Add source-tagged confidence scoring
- Add early-stop logic
- Expand social fallback to include Pinterest

## Phase 2 (Quality)

- Add domain-match preference logic
- Add optional MX validation + cache
- Refine filter and ranking

## Phase 3 (Observability)

- Full run metrics in progress/status APIs
- Tier A/B/C reporting in UI
- Top-leads ranking by confidence + lead score

## 15. Acceptance Criteria

A build is acceptable when:

1. For any run, every domain ends as `ok`, `no_contact`, or `error` (no silent drops)
2. Best contact fields are always populated consistently when contact exists
3. Tier A/B/C metrics are produced per run
4. Early stop activates when high-confidence email is found
5. Progress API reflects processed/remaining and contact counts live
6. System remains functional with zero paid services

## 16. Out of Scope (Current)

- Paid enrichment APIs
- Full SaaS multi-tenant architecture
- Managed queue infrastructure
- Automated outreach sending

---

This document is the implementation reference for the contact-intelligence roadmap.
