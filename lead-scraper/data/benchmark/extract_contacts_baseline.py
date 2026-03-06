#!/usr/bin/env python3
"""Tool 2: crawl discovered domains and extract contact intelligence."""

from __future__ import annotations

import argparse
import csv
import json
import random
import threading
import time
import urllib.parse
import urllib.robotparser
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

import requests
from bs4 import BeautifulSoup

from regex_utils import EMAIL_RE, SOCIAL_PATTERNS

try:
    import dns.resolver  # type: ignore
except Exception:  # pragma: no cover
    dns = None

CONTACT_HINTS = (
    "contact",
    "about",
    "support",
    "help",
    "legal",
    "privacy",
    "terms",
    "imprint",
    "impressum",
    "policy",
)
SEED_PATHS = (
    "/contact",
    "/pages/contact",
    "/about",
    "/pages/about",
    "/support",
    "/help",
    "/legal",
    "/terms",
    "/privacy",
    "/policies/privacy-policy",
    "/policies/contact-information",
)
EMAIL_DOMAIN_BLOCKLIST = {"shopify.com", "example.com", "test.com"}
EMAIL_LOCAL_BLOCKLIST = ("noreply", "no-reply", "donotreply", "example", "test")
BACKOFF_STEPS = (1, 2, 4)
HIGH_CONFIDENCE_SCORE = 95
EMAIL_SOURCE_SCORE = {"mailto": 100, "visible": 90, "policy": 80, "jsonld": 70, "obfuscated": 60}
PLATFORM_SIGNALS = {
    "shopify": ("cdn.shopify.com", "shopify.theme", "myshopify.com"),
    "woocommerce": ("wp-content/plugins/woocommerce", "woocommerce"),
    "magento": ("mage.cookies", "magento", "/static/version"),
    "bigcommerce": ("cdn.bc0a.com", "bigcommerce"),
}

UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]

_lock = threading.Lock()
_mx_lock = threading.Lock()


def normalize_base_url(raw: str) -> str | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    if not urllib.parse.urlparse(raw).scheme:
        raw = f"https://{raw}"
    parsed = urllib.parse.urlparse(raw)
    if not parsed.netloc:
        return None
    scheme = parsed.scheme.lower() if parsed.scheme else "https"
    netloc = parsed.netloc.lower()
    return f"{scheme}://{netloc}"


def unique(items: Iterable[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def ordered_unique(items: Iterable[str]) -> list[str]:
    return unique(items)


def looks_like_business_email(email: str) -> bool:
    e = email.strip().strip(".,;:!?)(").lower()
    parts = e.split("@")
    if len(parts) != 2:
        return False
    local, domain = parts
    if not local or not domain:
        return False
    if any(token in local for token in EMAIL_LOCAL_BLOCKLIST):
        return False
    if domain in EMAIL_DOMAIN_BLOCKLIST:
        return False
    if domain.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js")):
        return False
    return True


def clean_emails(matches: Iterable[str]) -> list[str]:
    cleaned = []
    for email in matches:
        e = email.strip().strip(".,;:!?)(").lower()
        if looks_like_business_email(e):
            cleaned.append(e)
    return unique(cleaned)


def extract_socials(html: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {k: [] for k in SOCIAL_PATTERNS}
    for name, pattern in SOCIAL_PATTERNS.items():
        for match in pattern.finditer(html):
            token = "/".join([g for g in match.groups() if g])
            found[name].append(token)
        found[name] = unique(found[name])
    return found


def detect_platform(full_text: str) -> str:
    body = full_text.lower()
    for platform, signals in PLATFORM_SIGNALS.items():
        if any(signal in body for signal in signals):
            return platform
    return "unknown"


def same_domain(url: str, base_domain: str) -> bool:
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return False
    return host == base_domain or host.endswith(f".{base_domain}")


def is_policy_page(url: str) -> bool:
    path = urllib.parse.urlparse(url).path.lower()
    return "/policies/" in path or any(token in path for token in ("privacy", "terms", "legal", "policy"))


def candidate_contact_links(base_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    base_host = urllib.parse.urlparse(base_url).netloc.lower()
    links: list[str] = []

    for seed in SEED_PATHS:
        links.append(urllib.parse.urljoin(base_url + "/", seed))

    for a in soup.select("a[href]"):
        href = (a.get("href") or "").strip()
        text = (a.get_text(" ", strip=True) or "").lower()
        href_lower = href.lower()

        if not href or href.startswith("#") or href.startswith("mailto:"):
            continue
        if not any(h in text or h in href_lower for h in CONTACT_HINTS):
            continue

        resolved = urllib.parse.urljoin(base_url, href)
        if same_domain(resolved, base_host):
            links.append(resolved.split("#")[0])

    return ordered_unique(links)


def can_fetch(base_url: str, user_agent: str) -> bool:
    robots_url = urllib.parse.urljoin(base_url + "/", "/robots.txt")
    parser = urllib.robotparser.RobotFileParser()
    try:
        parser.set_url(robots_url)
        parser.read()
        return parser.can_fetch(user_agent, base_url + "/")
    except Exception:
        return True


def fetch_with_retries(session: requests.Session, url: str, timeout: int) -> tuple[str | None, int]:
    retries_used = 0
    for attempt, backoff in enumerate(BACKOFF_STEPS, start=1):
        try:
            resp = session.get(url, timeout=timeout, allow_redirects=True)
            if resp.status_code >= 500:
                raise requests.HTTPError(f"status={resp.status_code}")
            if resp.status_code >= 400:
                return None, retries_used
            if "text/html" not in resp.headers.get("content-type", "").lower():
                return None, retries_used
            return resp.text, retries_used
        except requests.RequestException:
            if attempt < len(BACKOFF_STEPS):
                retries_used += 1
                time.sleep(backoff)
    return None, retries_used


def normalize_obfuscated_text(text: str) -> str:
    normalized = text
    replacements = {
        "[at]": "@",
        "(at)": "@",
        " at ": "@",
        "[dot]": ".",
        "(dot)": ".",
        " dot ": ".",
    }
    for src, dst in replacements.items():
        normalized = normalized.replace(src, dst)
        normalized = normalized.replace(src.upper(), dst)
    return normalized


def parse_mailto(soup: BeautifulSoup) -> list[str]:
    out: list[str] = []
    for anchor in soup.select("a[href]"):
        href = (anchor.get("href") or "").strip()
        if not href.lower().startswith("mailto:"):
            continue
        value = href.split(":", 1)[1].split("?", 1)[0].strip()
        if value:
            out.append(value)
    return clean_emails(out)


def parse_jsonld_emails(soup: BeautifulSoup) -> list[str]:
    emails: list[str] = []

    def collect(obj: Any) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key.lower() == "email" and isinstance(value, str):
                    emails.append(value)
                collect(value)
            return
        if isinstance(obj, list):
            for item in obj:
                collect(item)
            return
        if isinstance(obj, str):
            emails.extend(EMAIL_RE.findall(obj))

    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            # Handle malformed blocks by regex fallback.
            emails.extend(EMAIL_RE.findall(raw))
            continue
        collect(data)

    return clean_emails(emails)


def domain_match(email: str, site_domain: str) -> bool:
    try:
        email_domain = email.split("@", 1)[1].lower()
    except Exception:
        return False
    return email_domain == site_domain or email_domain.endswith(f".{site_domain}") or site_domain.endswith(f".{email_domain}")


def syntax_valid(email: str) -> bool:
    return bool(EMAIL_RE.fullmatch(email))


def validate_mx(domain: str, enabled: bool, cache: dict[str, bool]) -> bool | None:
    if not enabled:
        return None
    if dns is None:
        return None
    with _mx_lock:
        if domain in cache:
            return cache[domain]
    ok = False
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=5)  # type: ignore[attr-defined]
        ok = len(answers) > 0
    except Exception:
        ok = False
    with _mx_lock:
        cache[domain] = ok
    return ok


def score_candidate(source: str, email: str, site_domain: str) -> int:
    base = EMAIL_SOURCE_SCORE.get(source, 50)
    if domain_match(email, site_domain):
        base += 10
    return min(100, max(0, base))


def extract_email_candidates(page_url: str, html: str, site_domain: str) -> list[dict[str, Any]]:
    page_kind = "policy" if is_policy_page(page_url) else "standard"
    soup = BeautifulSoup(html, "html.parser")
    text_body = soup.get_text(" ", strip=True)
    normalized_text = normalize_obfuscated_text(text_body)

    candidates: list[dict[str, Any]] = []

    for email in parse_mailto(soup):
        candidates.append({"email": email, "source": "mailto", "page": page_url, "page_kind": page_kind})

    visible = clean_emails(EMAIL_RE.findall(text_body))
    for email in visible:
        source = "policy" if page_kind == "policy" else "visible"
        candidates.append({"email": email, "source": source, "page": page_url, "page_kind": page_kind})

    for email in parse_jsonld_emails(soup):
        candidates.append({"email": email, "source": "jsonld", "page": page_url, "page_kind": page_kind})

    obfuscated = clean_emails(EMAIL_RE.findall(normalized_text))
    for email in obfuscated:
        if email not in visible:
            source = "policy" if page_kind == "policy" else "obfuscated"
            candidates.append({"email": email, "source": source, "page": page_url, "page_kind": page_kind})

    dedup: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        email = candidate["email"]
        if not syntax_valid(email):
            continue
        candidate["score"] = score_candidate(candidate["source"], email, site_domain)
        previous = dedup.get(email)
        if not previous or candidate["score"] > previous["score"]:
            dedup[email] = candidate
    return list(dedup.values())


def choose_best_email(candidates: list[dict[str, Any]], site_domain: str, mx_enabled: bool, mx_cache: dict[str, bool]) -> dict[str, Any] | None:
    if not candidates:
        return None
    enriched: list[dict[str, Any]] = []
    for c in candidates:
        email = c["email"]
        email_domain = email.split("@", 1)[1]
        mx_ok = validate_mx(email_domain, mx_enabled, mx_cache)
        enriched.append(
            {
                **c,
                "email_valid_syntax": True,
                "email_valid_mx": mx_ok,
                "domain_match": domain_match(email, site_domain),
            }
        )
    enriched.sort(
        key=lambda x: (
            x.get("score", 0),
            1 if x.get("domain_match") else 0,
            1 if x.get("email_valid_mx") is True else 0,
        ),
        reverse=True,
    )
    return enriched[0]


def summarize_socials(social_map: dict[str, list[str]]) -> tuple[str, str, int]:
    priority = ("instagram", "facebook", "linkedin", "x", "tiktok", "pinterest")
    count = sum(1 for key in priority if social_map.get(key))
    for key in priority:
        values = social_map.get(key, [])
        if values:
            return f"social:{key}", values[0], count
    return "", "", count


def compute_lead_score(confidence_score: int, socials_count: int, platform: str) -> int:
    score = confidence_score
    score += min(20, socials_count * 5)
    if platform != "unknown":
        score += 10
    return min(120, score)


def process_domain(
    url: str,
    max_pages: int,
    timeout: int,
    min_delay: float,
    max_delay: float,
    early_stop_score: int,
    mx_enabled: bool,
    mx_cache: dict[str, bool],
) -> dict[str, Any]:
    started = time.perf_counter()
    base = normalize_base_url(url)
    if not base:
        return {"url": url, "domain": "", "status": "error", "tier": "tier_c", "error": "invalid_url"}

    base_domain = urllib.parse.urlparse(base).netloc.lower()
    user_agent = random.choice(UAS)
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})

    if not can_fetch(base, user_agent):
        return {"url": base, "domain": base_domain, "status": "error", "tier": "tier_c", "error": "blocked_by_robots"}

    pages_to_scan: list[str] = [base]
    queued = set(pages_to_scan)
    scanned: set[str] = set()
    all_html: list[str] = []
    email_candidates: list[dict[str, Any]] = []
    retries_used_total = 0

    while pages_to_scan and len(scanned) < max_pages:
        target = pages_to_scan.pop(0)
        if target in scanned:
            continue
        scanned.add(target)

        html, retries_used = fetch_with_retries(session, target, timeout=timeout)
        retries_used_total += retries_used
        if not html:
            continue

        all_html.append(html)
        email_candidates.extend(extract_email_candidates(target, html, base_domain))

        if len(all_html) == 1:
            for candidate in candidate_contact_links(base, html):
                if candidate not in queued and candidate not in scanned:
                    pages_to_scan.append(candidate)
                    queued.add(candidate)

        best_now = choose_best_email(email_candidates, base_domain, mx_enabled=mx_enabled, mx_cache=mx_cache)
        if best_now and best_now.get("score", 0) >= early_stop_score:
            break

        time.sleep(random.uniform(min_delay, max_delay))

    full_text = "\n".join(all_html)
    platform = detect_platform(full_text)
    social_map: dict[str, list[str]] = {k: [] for k in SOCIAL_PATTERNS}
    for html in all_html:
        partial = extract_socials(html)
        for key, values in partial.items():
            social_map[key].extend(values)
    social_map = {k: unique(v) for k, v in social_map.items()}

    best_email = choose_best_email(email_candidates, base_domain, mx_enabled=mx_enabled, mx_cache=mx_cache)
    all_emails = unique([c["email"] for c in email_candidates])

    best_contact_type = ""
    best_contact_value = ""
    confidence_score = 0
    email_primary = ""
    email_source = ""
    email_valid_syntax = False
    email_valid_mx: bool | None = None

    if best_email:
        email_primary = best_email["email"]
        email_source = best_email["source"]
        email_valid_syntax = bool(best_email.get("email_valid_syntax"))
        email_valid_mx = best_email.get("email_valid_mx")
        confidence_score = int(best_email.get("score", 0))
        best_contact_type = "email"
        best_contact_value = email_primary
    else:
        social_type, social_value, _ = summarize_socials(social_map)
        if social_value:
            best_contact_type = social_type
            best_contact_value = social_value
            confidence_score = 40

    _, _, socials_count = summarize_socials(social_map)
    lead_score = compute_lead_score(confidence_score, socials_count, platform)

    if email_primary:
        tier = "tier_a"
        status = "ok"
    elif socials_count > 0:
        tier = "tier_b"
        status = "ok"
    else:
        tier = "tier_c"
        status = "no_contact"

    crawl_ms = int((time.perf_counter() - started) * 1000)
    return {
        "url": base,
        "domain": base_domain,
        "best_contact_type": best_contact_type,
        "best_contact_value": best_contact_value,
        "confidence_score": confidence_score,
        "email_primary": email_primary,
        "email_all": all_emails,
        "email_source": email_source,
        "email_valid_syntax": email_valid_syntax,
        "email_valid_mx": email_valid_mx,
        "platform": platform,
        "status": status,
        "tier": tier,
        "lead_score": lead_score,
        "pages_scanned": len(all_html),
        "crawl_ms": crawl_ms,
        "retries_used": retries_used_total,
        "socials": social_map,
        "error": "",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def read_targets(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Targets file not found: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    return unique([line.strip() for line in lines if line.strip() and not line.startswith("#")])


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        for row in rows:
            fp.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(
            [
                "domain",
                "url",
                "best_contact_type",
                "best_contact_value",
                "confidence_score",
                "email_primary",
                "email_all",
                "email_source",
                "email_valid_syntax",
                "email_valid_mx",
                "instagram",
                "facebook",
                "linkedin",
                "x",
                "tiktok",
                "pinterest",
                "platform",
                "status",
                "tier",
                "lead_score",
                "pages_scanned",
                "crawl_ms",
                "retries_used",
                "error",
            ]
        )
        for row in rows:
            socials = row.get("socials", {})
            writer.writerow(
                [
                    row.get("domain", ""),
                    row.get("url", ""),
                    row.get("best_contact_type", ""),
                    row.get("best_contact_value", ""),
                    row.get("confidence_score", 0),
                    row.get("email_primary", ""),
                    ";".join(row.get("email_all", [])),
                    row.get("email_source", ""),
                    row.get("email_valid_syntax", False),
                    row.get("email_valid_mx", ""),
                    ";".join(socials.get("instagram", [])),
                    ";".join(socials.get("facebook", [])),
                    ";".join(socials.get("linkedin", [])),
                    ";".join(socials.get("x", [])),
                    ";".join(socials.get("tiktok", [])),
                    ";".join(socials.get("pinterest", [])),
                    row.get("platform", "unknown"),
                    row.get("status", ""),
                    row.get("tier", ""),
                    row.get("lead_score", 0),
                    row.get("pages_scanned", 0),
                    row.get("crawl_ms", 0),
                    row.get("retries_used", 0),
                    row.get("error", ""),
                ]
            )


def write_progress(path: Path | None, payload: dict[str, Any]) -> None:
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_mx_cache(path: Path) -> dict[str, bool]:
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return {str(k): bool(v) for k, v in parsed.items()}
    except Exception:
        return {}
    return {}


def save_mx_cache(path: Path, cache: dict[str, bool]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def compute_rates(stats: dict[str, float], total: int) -> dict[str, float]:
    if total <= 0:
        return {"pct_tier_a": 0.0, "pct_tier_b": 0.0, "pct_tier_c": 0.0}
    return {
        "pct_tier_a": round((stats["tier_a"] / total) * 100, 2),
        "pct_tier_b": round((stats["tier_b"] / total) * 100, 2),
        "pct_tier_c": round((stats["tier_c"] / total) * 100, 2),
    }


def build_progress_payload(stats: dict[str, float], total: int, running: bool) -> dict[str, Any]:
    rates = compute_rates(stats, total)
    processed = int(stats["processed"])
    avg_pages = round((stats["total_pages_scanned"] / processed), 2) if processed else 0.0
    avg_seconds = round((stats["total_crawl_seconds"] / processed), 2) if processed else 0.0
    return {
        "running": running,
        "domains_total": total,
        "total": total,
        "domains_processed": processed,
        "processed": processed,
        "remaining": max(0, total - processed),
        "emails_found": int(stats["emails_found"]),
        "ok": int(stats["ok"]),
        "no_contact": int(stats["no_contact"]),
        "error": int(stats["error"]),
        "tier_a": int(stats["tier_a"]),
        "tier_b": int(stats["tier_b"]),
        "tier_c": int(stats["tier_c"]),
        "pct_tier_a": rates["pct_tier_a"],
        "pct_tier_b": rates["pct_tier_b"],
        "pct_tier_c": rates["pct_tier_c"],
        "avg_pages_scanned": avg_pages,
        "avg_seconds_per_domain": avg_seconds,
        "retries_used_total": int(stats["retries_used_total"]),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract emails and social handles from discovered targets.")
    parser.add_argument("--input", type=Path, default=Path("lead-scraper/data/targets.txt"), help="Path to targets file.")
    parser.add_argument("--output-jsonl", type=Path, default=Path("lead-scraper/data/results.jsonl"), help="Output JSONL file.")
    parser.add_argument("--output-csv", type=Path, default=Path("lead-scraper/data/results.csv"), help="Output CSV file.")
    parser.add_argument(
        "--progress-file",
        type=Path,
        default=Path("lead-scraper/data/progress.json"),
        help="Progress JSON file for live UI status.",
    )
    parser.add_argument("--workers", type=int, default=5, help="Concurrent domains to process.")
    parser.add_argument("--max-pages", type=int, default=5, help="Max pages per domain.")
    parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout in seconds.")
    parser.add_argument("--min-delay", type=float, default=0.7, help="Minimum delay between page hits per domain.")
    parser.add_argument("--max-delay", type=float, default=1.8, help="Maximum delay between page hits per domain.")
    parser.add_argument(
        "--early-stop-score",
        type=int,
        default=HIGH_CONFIDENCE_SCORE,
        help="Stop scanning a domain once best email reaches this confidence.",
    )
    parser.add_argument(
        "--mx-validation",
        action="store_true",
        help="Enable MX record validation (optional, slower).",
    )
    parser.add_argument(
        "--mx-cache-file",
        type=Path,
        default=Path("lead-scraper/data/mx_cache.json"),
        help="Path to MX cache file when validation is enabled.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    targets = read_targets(args.input)
    if not targets:
        raise SystemExit("No targets found in input file.")

    total = len(targets)
    stats: dict[str, float] = {
        "processed": 0,
        "emails_found": 0,
        "ok": 0,
        "no_contact": 0,
        "error": 0,
        "tier_a": 0,
        "tier_b": 0,
        "tier_c": 0,
        "total_pages_scanned": 0,
        "total_crawl_seconds": 0,
        "retries_used_total": 0,
    }
    mx_cache = load_mx_cache(args.mx_cache_file) if args.mx_validation else {}
    write_progress(args.progress_file, build_progress_payload(stats, total, running=True))

    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [
            pool.submit(
                process_domain,
                url=target,
                max_pages=max(1, args.max_pages),
                timeout=max(5, args.timeout),
                min_delay=max(0.0, args.min_delay),
                max_delay=max(args.min_delay, args.max_delay),
                early_stop_score=max(60, min(100, args.early_stop_score)),
                mx_enabled=args.mx_validation,
                mx_cache=mx_cache,
            )
            for target in targets
        ]
        for fut in as_completed(futures):
            row = fut.result()
            with _lock:
                rows.append(row)
                stats["processed"] += 1
                stats["emails_found"] += len(row.get("email_all", []))
                stats["total_pages_scanned"] += row.get("pages_scanned", 0)
                stats["total_crawl_seconds"] += row.get("crawl_ms", 0) / 1000
                stats["retries_used_total"] += row.get("retries_used", 0)
                status = row.get("status", "error")
                tier = row.get("tier", "tier_c")
                if status in {"ok", "no_contact", "error"}:
                    stats[status] += 1
                else:
                    stats["error"] += 1
                if tier in {"tier_a", "tier_b", "tier_c"}:
                    stats[tier] += 1
                else:
                    stats["tier_c"] += 1

                write_progress(args.progress_file, build_progress_payload(stats, total, running=True))
                print(
                    f"[done] {row.get('domain', row.get('url', ''))} "
                    f"best={row.get('best_contact_type', '')} "
                    f"conf={row.get('confidence_score', 0)} "
                    f"tier={row.get('tier', '')}"
                )

    rows.sort(key=lambda r: r.get("domain", ""))
    write_jsonl(args.output_jsonl, rows)
    write_csv(args.output_csv, rows)
    write_progress(args.progress_file, build_progress_payload(stats, total, running=False))
    if args.mx_validation:
        save_mx_cache(args.mx_cache_file, mx_cache)

    print(
        json.dumps(
            {
                "processed": len(rows),
                "jsonl": str(args.output_jsonl),
                "csv": str(args.output_csv),
                "emails_found": int(stats["emails_found"]),
                "tier_a": int(stats["tier_a"]),
                "tier_b": int(stats["tier_b"]),
                "tier_c": int(stats["tier_c"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
