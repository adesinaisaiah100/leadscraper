#!/usr/bin/env python3
"""Tool 2: crawl discovered domains and extract contact intelligence."""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import threading
import time
import urllib.parse
import urllib.robotparser
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

import requests
from bs4 import BeautifulSoup

from queue_store import QueueStore
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
    "team",
)
PRIORITY_PATH_HINTS = ("/contact", "/about", "/support", "/help", "/team", "/legal", "/privacy", "/terms", "/policy")
SEED_PATHS = (
    "/contact",
    "/pages/contact",
    "/about",
    "/pages/about",
    "/support",
    "/help",
    "/team",
    "/legal",
    "/terms",
    "/privacy",
    "/policies/privacy-policy",
    "/policies/contact-information",
)
BUSINESS_GUESS_LOCALS = ("info", "contact", "hello", "support", "sales")
RISKY_EMAIL_LOCALS = {"info", "contact", "hello", "support", "sales", "admin"}
EMAIL_DOMAIN_BLOCKLIST = {"shopify.com", "example.com", "test.com"}
EMAIL_LOCAL_BLOCKLIST = ("noreply", "no-reply", "donotreply", "example", "test")
BACKOFF_STEPS = (1, 2, 4)
HIGH_CONFIDENCE_SCORE = 95
EMAIL_SOURCE_SCORE = {
    "mailto": 100,
    "visible": 90,
    "policy": 80,
    "jsonld": 70,
    "obfuscated": 60,
    "social_profile": 55,
    "domain_guess": 50,
}
PLATFORM_SIGNALS = {
    "shopify": ("cdn.shopify.com", "shopify.theme", "myshopify.com"),
    "woocommerce": ("wp-content/plugins/woocommerce", "woocommerce"),
    "magento": ("mage.cookies", "magento", "/static/version"),
    "bigcommerce": ("cdn.bc0a.com", "bigcommerce"),
}
SOCIAL_DOMAINS = {
    "instagram": ("instagram.com",),
    "facebook": ("facebook.com",),
    "linkedin": ("linkedin.com",),
    "x": ("x.com", "twitter.com"),
    "tiktok": ("tiktok.com",),
    "pinterest": ("pinterest.com",),
}
MAX_SITEMAPS_TO_PARSE = 5
MAX_SITEMAP_URLS = 400
MAX_SOCIAL_PROFILE_FETCHES = 4

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


def is_priority_path(url: str) -> bool:
    path = urllib.parse.urlparse(url).path.lower()
    if path in {"", "/"}:
        return False
    return any(hint in path for hint in PRIORITY_PATH_HINTS)


def normalize_link(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", "", "", ""))


def candidate_contact_links(base_url: str, html: str, include_seed_paths: bool = False) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    base_host = urllib.parse.urlparse(base_url).netloc.lower()
    links: list[str] = []

    if include_seed_paths:
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
            links.append(normalize_link(resolved.split("#")[0]))

    return ordered_unique(links)


def extract_social_profile_urls(page_url: str, html: str) -> dict[str, list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    out: dict[str, list[str]] = {k: [] for k in SOCIAL_DOMAINS}
    for anchor in soup.select("a[href]"):
        href = (anchor.get("href") or "").strip()
        if not href:
            continue
        resolved = urllib.parse.urljoin(page_url, href)
        parsed = urllib.parse.urlparse(resolved)
        host = parsed.netloc.lower()
        if not host:
            continue
        clean = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
        for platform, domains in SOCIAL_DOMAINS.items():
            if any(domain in host for domain in domains):
                out[platform].append(clean)
    return {k: unique(v) for k, v in out.items()}


def can_fetch(base_url: str, user_agent: str) -> bool:
    robots_url = urllib.parse.urljoin(base_url + "/", "/robots.txt")
    parser = urllib.robotparser.RobotFileParser()
    try:
        parser.set_url(robots_url)
        parser.read()
        return parser.can_fetch(user_agent, base_url + "/")
    except Exception:
        return True


def fetch_response_with_retries(session: requests.Session, url: str, timeout: int) -> tuple[requests.Response | None, int]:
    retries_used = 0
    for attempt, backoff in enumerate(BACKOFF_STEPS, start=1):
        try:
            resp = session.get(url, timeout=timeout, allow_redirects=True)
            if resp.status_code >= 500:
                raise requests.HTTPError(f"status={resp.status_code}")
            return resp, retries_used
        except requests.RequestException:
            if attempt < len(BACKOFF_STEPS):
                retries_used += 1
                time.sleep(backoff)
    return None, retries_used


def fetch_html_with_retries(session: requests.Session, url: str, timeout: int) -> tuple[str | None, int]:
    resp, retries_used = fetch_response_with_retries(session, url, timeout)
    if not resp or resp.status_code >= 400:
        return None, retries_used
    body = resp.text or ""
    content_type = resp.headers.get("content-type", "").lower()
    if "text/html" not in content_type and "<html" not in body[:400].lower():
        return None, retries_used
    return body, retries_used


def _tag_name(tag: str) -> str:
    return tag.split("}", 1)[1].lower() if "}" in tag else tag.lower()


def parse_sitemap_xml(xml_text: str) -> tuple[list[str], list[str]]:
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return [], []

    urls: list[str] = []
    sitemaps: list[str] = []
    root_name = _tag_name(root.tag)
    if root_name == "urlset":
        for node in root:
            if _tag_name(node.tag) != "url":
                continue
            for child in node:
                if _tag_name(child.tag) == "loc" and child.text:
                    urls.append(child.text.strip())
    elif root_name == "sitemapindex":
        for node in root:
            if _tag_name(node.tag) != "sitemap":
                continue
            for child in node:
                if _tag_name(child.tag) == "loc" and child.text:
                    sitemaps.append(child.text.strip())
    return urls, sitemaps


def fetch_sitemap_targets(
    session: requests.Session,
    base_url: str,
    base_domain: str,
    timeout: int,
) -> tuple[list[str], list[str], int, int]:
    queue = [urllib.parse.urljoin(base_url + "/", "/sitemap.xml")]
    visited: set[str] = set()
    discovered: list[str] = []
    retries_total = 0

    while queue and len(visited) < MAX_SITEMAPS_TO_PARSE and len(discovered) < MAX_SITEMAP_URLS:
        sitemap_url = normalize_link(queue.pop(0))
        if sitemap_url in visited:
            continue
        visited.add(sitemap_url)

        resp, retries_used = fetch_response_with_retries(session, sitemap_url, timeout)
        retries_total += retries_used
        if not resp or resp.status_code != 200:
            continue
        body = (resp.text or "").strip()
        content_type = resp.headers.get("content-type", "").lower()
        if "xml" not in content_type and not body.startswith("<"):
            continue

        page_urls, nested_sitemaps = parse_sitemap_xml(body)
        for loc in page_urls:
            clean = normalize_link(loc)
            if same_domain(clean, base_domain):
                discovered.append(clean)
                if len(discovered) >= MAX_SITEMAP_URLS:
                    break

        for nested in nested_sitemaps:
            clean_nested = normalize_link(nested)
            if same_domain(clean_nested, base_domain) and clean_nested not in visited:
                queue.append(clean_nested)

    deduped = unique(discovered)
    priority_urls = [u for u in deduped if is_priority_path(u)]
    generic_urls = [u for u in deduped if not is_priority_path(u)]
    return priority_urls, generic_urls, len(deduped), retries_total


def normalize_obfuscated_text(text: str) -> str:
    normalized = text
    patterns = (
        (r"(?i)\[\s*at\s*\]", "@"),
        (r"(?i)\(\s*at\s*\)", "@"),
        (r"(?i)\s+at\s+", "@"),
        (r"(?i)\[\s*dot\s*\]", "."),
        (r"(?i)\(\s*dot\s*\)", "."),
        (r"(?i)\s+dot\s+", "."),
    )
    for pattern, replacement in patterns:
        normalized = re.sub(pattern, replacement, normalized)
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


def extract_email_candidates(page_url: str, html: str, site_domain: str, source_page_type: str) -> list[dict[str, Any]]:
    page_kind = "policy" if is_policy_page(page_url) else "standard"
    soup = BeautifulSoup(html, "html.parser")
    text_body = soup.get_text(" ", strip=True)
    normalized_text = normalize_obfuscated_text(text_body)

    candidates: list[dict[str, Any]] = []

    for email in parse_mailto(soup):
        candidates.append(
            {"email": email, "source": "mailto", "page": page_url, "page_kind": page_kind, "source_page_type": source_page_type}
        )

    visible = clean_emails(EMAIL_RE.findall(text_body))
    for email in visible:
        source = "policy" if page_kind == "policy" else "visible"
        candidates.append(
            {"email": email, "source": source, "page": page_url, "page_kind": page_kind, "source_page_type": source_page_type}
        )

    for email in parse_jsonld_emails(soup):
        candidates.append(
            {"email": email, "source": "jsonld", "page": page_url, "page_kind": page_kind, "source_page_type": source_page_type}
        )

    obfuscated = clean_emails(EMAIL_RE.findall(normalized_text))
    for email in obfuscated:
        if email not in visible:
            source = "policy" if page_kind == "policy" else "obfuscated"
            candidates.append(
                {"email": email, "source": source, "page": page_url, "page_kind": page_kind, "source_page_type": source_page_type}
            )

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


def build_domain_guess_candidates(site_domain: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for local in BUSINESS_GUESS_LOCALS:
        email = f"{local}@{site_domain}".lower()
        if syntax_valid(email) and looks_like_business_email(email):
            out.append(
                {
                    "email": email,
                    "source": "domain_guess",
                    "page": "",
                    "page_kind": "guess",
                    "source_page_type": "domain_guess",
                    "score": score_candidate("domain_guess", email, site_domain),
                }
            )
    return out


def extract_social_profile_email_candidates(
    session: requests.Session,
    social_url_map: dict[str, list[str]],
    timeout: int,
    site_domain: str,
) -> tuple[list[dict[str, Any]], int]:
    profile_urls: list[str] = []
    for platform in ("instagram", "facebook", "linkedin", "x", "tiktok", "pinterest"):
        urls = social_url_map.get(platform, [])
        if urls:
            profile_urls.append(urls[0])
    profile_urls = profile_urls[:MAX_SOCIAL_PROFILE_FETCHES]

    retries_total = 0
    candidates: list[dict[str, Any]] = []
    for profile_url in profile_urls:
        html, retries_used = fetch_html_with_retries(session, profile_url, timeout)
        retries_total += retries_used
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        text_body = soup.get_text(" ", strip=True)
        normalized_text = normalize_obfuscated_text(text_body)
        found = clean_emails(EMAIL_RE.findall(text_body) + EMAIL_RE.findall(normalized_text))
        for email in found:
            candidates.append(
                {
                    "email": email,
                    "source": "social_profile",
                    "page": profile_url,
                    "page_kind": "social_profile",
                    "source_page_type": "social_profile",
                }
            )

    dedup: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        email = candidate["email"]
        if not syntax_valid(email):
            continue
        candidate["score"] = score_candidate(candidate["source"], email, site_domain)
        previous = dedup.get(email)
        if not previous or candidate["score"] > previous["score"]:
            dedup[email] = candidate

    return list(dedup.values()), retries_total


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


def parse_quality_flags(raw: str) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split("|") if part.strip()]


def email_local_part(email: str) -> str:
    try:
        return email.split("@", 1)[0].lower()
    except Exception:
        return ""


def is_quality_gate_blocked(is_healthy: bool, quality_flags: list[str]) -> bool:
    blocked_flags = {"parked_page", "placeholder_page", "fetch_failed"}
    if not is_healthy:
        return True
    if any(flag in blocked_flags for flag in quality_flags):
        return True
    return any(flag.startswith("status_4") or flag.startswith("status_5") for flag in quality_flags)


def compute_lead_score_v2(
    discovery_quality_score: int,
    contact_confidence_score: int,
    email_primary: str,
    email_source: str,
    quality_gate_blocked: bool,
) -> int:
    score = round((0.3 * discovery_quality_score) + (0.7 * contact_confidence_score))
    if email_primary:
        if email_local_part(email_primary) in RISKY_EMAIL_LOCALS:
            score -= 5
        if email_source == "domain_guess":
            score -= 5
    if quality_gate_blocked:
        score -= 20
    return max(0, min(100, score))


def process_domain(
    url: str,
    target_meta: dict[str, Any],
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

    queued = {normalize_link(base)}
    scanned: set[str] = set()
    all_html: list[str] = []
    email_candidates: list[dict[str, Any]] = []
    retries_used_total = 0
    priority_pages_scanned = 0
    sitemap_urls_examined = 0
    priority_queue: list[tuple[str, str]] = []
    generic_queue: list[tuple[str, str]] = []
    social_url_map: dict[str, list[str]] = {k: [] for k in SOCIAL_DOMAINS}

    homepage_html, retries_used = fetch_html_with_retries(session, base, timeout=timeout)
    retries_used_total += retries_used
    if homepage_html:
        all_html.append(homepage_html)
        scanned.add(normalize_link(base))
        email_candidates.extend(extract_email_candidates(base, homepage_html, base_domain, source_page_type="homepage"))

        profile_links = extract_social_profile_urls(base, homepage_html)
        for key, values in profile_links.items():
            social_url_map[key].extend(values)

        for candidate in candidate_contact_links(base, homepage_html, include_seed_paths=True):
            candidate_type = "priority" if is_priority_path(candidate) else "generic"
            clean_candidate = normalize_link(candidate)
            if clean_candidate not in queued and clean_candidate not in scanned:
                if candidate_type == "priority":
                    priority_queue.append((clean_candidate, candidate_type))
                else:
                    generic_queue.append((clean_candidate, candidate_type))
                queued.add(clean_candidate)

    sitemap_priority, sitemap_generic, sitemap_examined_count, sitemap_retries = fetch_sitemap_targets(
        session=session,
        base_url=base,
        base_domain=base_domain,
        timeout=timeout,
    )
    sitemap_urls_examined += sitemap_examined_count
    retries_used_total += sitemap_retries
    for candidate in sitemap_priority:
        clean_candidate = normalize_link(candidate)
        if clean_candidate not in queued and clean_candidate not in scanned:
            priority_queue.append((clean_candidate, "sitemap_priority"))
            queued.add(clean_candidate)
    for candidate in sitemap_generic:
        clean_candidate = normalize_link(candidate)
        if clean_candidate not in queued and clean_candidate not in scanned:
            generic_queue.append((clean_candidate, "sitemap_generic"))
            queued.add(clean_candidate)

    best_now = choose_best_email(email_candidates, base_domain, mx_enabled=mx_enabled, mx_cache=mx_cache)
    while (priority_queue or generic_queue) and len(scanned) < max_pages:
        if best_now and best_now.get("score", 0) >= early_stop_score:
            break
        if priority_queue:
            target, source_page_type = priority_queue.pop(0)
        else:
            target, source_page_type = generic_queue.pop(0)
        if target in scanned:
            continue
        scanned.add(target)

        html, retries_used = fetch_html_with_retries(session, target, timeout=timeout)
        retries_used_total += retries_used
        if not html:
            continue

        all_html.append(html)
        if source_page_type in {"priority", "sitemap_priority"}:
            priority_pages_scanned += 1
        email_candidates.extend(extract_email_candidates(target, html, base_domain, source_page_type=source_page_type))

        profile_links = extract_social_profile_urls(target, html)
        for key, values in profile_links.items():
            social_url_map[key].extend(values)

        for discovered in candidate_contact_links(base, html, include_seed_paths=False):
            discovered_type = "priority" if is_priority_path(discovered) else "generic"
            clean_discovered = normalize_link(discovered)
            if clean_discovered not in queued and clean_discovered not in scanned:
                if discovered_type == "priority":
                    priority_queue.append((clean_discovered, discovered_type))
                else:
                    generic_queue.append((clean_discovered, discovered_type))
                queued.add(clean_discovered)

        best_now = choose_best_email(email_candidates, base_domain, mx_enabled=mx_enabled, mx_cache=mx_cache)
        if best_now and best_now.get("score", 0) >= early_stop_score:
            break

        time.sleep(random.uniform(min_delay, max_delay))

    social_candidates, social_retries = extract_social_profile_email_candidates(
        session=session,
        social_url_map={k: unique(v) for k, v in social_url_map.items()},
        timeout=timeout,
        site_domain=base_domain,
    )
    retries_used_total += social_retries
    email_candidates.extend(social_candidates)
    email_candidates.extend(build_domain_guess_candidates(base_domain))

    full_text = "\n".join(all_html)
    platform = detect_platform(full_text)
    social_map: dict[str, list[str]] = {k: [] for k in SOCIAL_PATTERNS}
    for html in all_html:
        partial = extract_socials(html)
        for key, values in partial.items():
            social_map[key].extend(values)
    for key, values in social_url_map.items():
        social_map[key].extend(values)
    social_map = {k: unique(v) for k, v in social_map.items()}

    best_email = choose_best_email(email_candidates, base_domain, mx_enabled=mx_enabled, mx_cache=mx_cache)
    all_emails = unique([c["email"] for c in email_candidates])

    best_contact_type = ""
    best_contact_value = ""
    confidence_score = 0
    email_primary = ""
    email_source = ""
    source_page_type = ""
    email_valid_syntax = False
    email_valid_mx: bool | None = None

    if best_email:
        email_primary = best_email["email"]
        email_source = best_email["source"]
        source_page_type = best_email.get("source_page_type", "")
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
            source_page_type = "social"

    _, _, socials_count = summarize_socials(social_map)
    discovery_quality_score = int(target_meta.get("discovery_quality_score", 0) or 0)
    is_healthy = bool(target_meta.get("is_healthy", False))
    quality_flags = parse_quality_flags(str(target_meta.get("quality_flags", "")))
    quality_gate_blocked = is_quality_gate_blocked(is_healthy, quality_flags)
    contact_confidence_score = confidence_score

    lead_score = compute_lead_score(confidence_score, socials_count, platform)
    lead_score_v2 = compute_lead_score_v2(
        discovery_quality_score=discovery_quality_score,
        contact_confidence_score=contact_confidence_score,
        email_primary=email_primary,
        email_source=email_source,
        quality_gate_blocked=quality_gate_blocked,
    )

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
        "source_page_type": source_page_type,
        "email_valid_syntax": email_valid_syntax,
        "email_valid_mx": email_valid_mx,
        "platform": platform,
        "platform_detected": str(target_meta.get("platform_detected", "unknown") or "unknown"),
        "status": status,
        "tier": tier,
        "discovery_quality_score": discovery_quality_score,
        "contact_confidence_score": contact_confidence_score,
        "lead_score": lead_score,
        "lead_score_v2": lead_score_v2,
        "quality_flags": quality_flags,
        "is_healthy": is_healthy,
        "quality_gate_pass": not quality_gate_blocked,
        "pages_scanned": len(all_html),
        "priority_pages_scanned": priority_pages_scanned,
        "sitemap_urls_examined": sitemap_urls_examined,
        "crawl_ms": crawl_ms,
        "retries_used": retries_used_total,
        "socials": social_map,
        "error": "",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def load_discovery_metadata(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_url: dict[str, dict[str, Any]] = {}
    by_domain: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return by_url, by_domain

    with path.open("r", encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            raw_url = (row.get("url") or "").strip()
            clean_url = normalize_base_url(raw_url)
            if not clean_url:
                continue
            domain = urllib.parse.urlparse(clean_url).netloc.lower()
            metadata = {
                "discovery_quality_score": int(str(row.get("target_quality_score", "0") or "0") or 0),
                "quality_flags": str(row.get("quality_flags", "") or ""),
                "is_healthy": parse_bool(str(row.get("is_healthy", "false") or "false")),
                "platform_detected": str(row.get("platform_detected", "unknown") or "unknown"),
            }
            by_url[clean_url] = metadata
            by_domain[domain] = metadata
    return by_url, by_domain


def read_target_records(input_path: Path, targets_csv: Path) -> list[dict[str, Any]]:
    if not input_path.exists():
        raise FileNotFoundError(f"Targets file not found: {input_path}")

    meta_by_url, meta_by_domain = load_discovery_metadata(targets_csv)
    lines = input_path.read_text(encoding="utf-8").splitlines()
    urls = unique([line.strip() for line in lines if line.strip() and not line.startswith("#")])
    records: list[dict[str, Any]] = []
    for raw_url in urls:
        clean_url = normalize_base_url(raw_url)
        if not clean_url:
            continue
        domain = urllib.parse.urlparse(clean_url).netloc.lower()
        meta = meta_by_url.get(clean_url) or meta_by_domain.get(domain) or {}
        records.append(
            {
                "url": clean_url,
                "domain": domain,
                "discovery_quality_score": int(meta.get("discovery_quality_score", 0) or 0),
                "quality_flags": str(meta.get("quality_flags", "")),
                "is_healthy": bool(meta.get("is_healthy", False)),
                "platform_detected": str(meta.get("platform_detected", "unknown") or "unknown"),
            }
        )
    return records


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
                "source_page_type",
                "email_valid_syntax",
                "email_valid_mx",
                "instagram",
                "facebook",
                "linkedin",
                "x",
                "tiktok",
                "pinterest",
                "platform",
                "platform_detected",
                "status",
                "tier",
                "discovery_quality_score",
                "contact_confidence_score",
                "lead_score",
                "lead_score_v2",
                "quality_flags",
                "is_healthy",
                "quality_gate_pass",
                "pages_scanned",
                "priority_pages_scanned",
                "sitemap_urls_examined",
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
                    row.get("source_page_type", ""),
                    row.get("email_valid_syntax", False),
                    row.get("email_valid_mx", ""),
                    ";".join(socials.get("instagram", [])),
                    ";".join(socials.get("facebook", [])),
                    ";".join(socials.get("linkedin", [])),
                    ";".join(socials.get("x", [])),
                    ";".join(socials.get("tiktok", [])),
                    ";".join(socials.get("pinterest", [])),
                    row.get("platform", "unknown"),
                    row.get("platform_detected", "unknown"),
                    row.get("status", ""),
                    row.get("tier", ""),
                    row.get("discovery_quality_score", 0),
                    row.get("contact_confidence_score", 0),
                    row.get("lead_score", 0),
                    row.get("lead_score_v2", 0),
                    "|".join(row.get("quality_flags", [])),
                    str(bool(row.get("is_healthy", False))).lower(),
                    str(bool(row.get("quality_gate_pass", False))).lower(),
                    row.get("pages_scanned", 0),
                    row.get("priority_pages_scanned", 0),
                    row.get("sitemap_urls_examined", 0),
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


def build_progress_payload(
    stats: dict[str, float],
    total: int,
    running: bool,
    queue_counts: dict[str, int] | None = None,
    success_rate_by_source: dict[str, float] | None = None,
    success_rate_by_platform: dict[str, float] | None = None,
    fail_reasons_distribution: dict[str, int] | None = None,
) -> dict[str, Any]:
    rates = compute_rates(stats, total)
    processed = int(stats["processed"])
    avg_pages = round((stats["total_pages_scanned"] / processed), 2) if processed else 0.0
    avg_seconds = round((stats["total_crawl_seconds"] / processed), 2) if processed else 0.0
    elapsed_minutes = max(1e-6, stats.get("elapsed_minutes", 0.0))
    throughput_domains_per_minute = round(processed / elapsed_minutes, 2) if processed else 0.0
    queue_counts = queue_counts or {"pending": 0, "processing": 0, "completed": 0, "failed": 0, "total": total}
    return {
        "running": running,
        "domains_total": int(queue_counts.get("total", total)),
        "total": int(queue_counts.get("total", total)),
        "domains_processed": int(queue_counts.get("completed", 0) + queue_counts.get("failed", 0)),
        "processed": processed,
        "remaining": int(queue_counts.get("pending", 0) + queue_counts.get("processing", 0)),
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
        "priority_pages_scanned": int(stats["priority_pages_scanned_total"]),
        "sitemap_urls_examined": int(stats["sitemap_urls_examined_total"]),
        "retries_used_total": int(stats["retries_used_total"]),
        "queue_pending": int(queue_counts.get("pending", 0)),
        "queue_processing": int(queue_counts.get("processing", 0)),
        "queue_completed": int(queue_counts.get("completed", 0)),
        "queue_failed": int(queue_counts.get("failed", 0)),
        "throughput_domains_per_minute": throughput_domains_per_minute,
        "success_rate_by_source": success_rate_by_source or {},
        "success_rate_by_platform": success_rate_by_platform or {},
        "fail_reasons_distribution": fail_reasons_distribution or {},
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def summarize_success_rates(rows: list[dict[str, Any]]) -> tuple[dict[str, float], dict[str, float]]:
    ok_rows = [row for row in rows if str(row.get("status", "")).lower() == "ok"]
    source_counts: dict[str, int] = {}
    platform_counts: dict[str, int] = {}
    for row in ok_rows:
        source = str(row.get("email_source", "") or "social_only").lower()
        platform = str(row.get("platform", "unknown") or "unknown").lower()
        source_counts[source] = source_counts.get(source, 0) + 1
        platform_counts[platform] = platform_counts.get(platform, 0) + 1

    total_ok = max(1, len(ok_rows))
    source_rates = {k: round((v / total_ok) * 100, 2) for k, v in source_counts.items()}
    platform_rates = {k: round((v / total_ok) * 100, 2) for k, v in platform_counts.items()}
    return source_rates, platform_rates


def apply_row_stats(stats: dict[str, float], row: dict[str, Any]) -> None:
    stats["processed"] += 1
    stats["emails_found"] += len(row.get("email_all", []))
    stats["total_pages_scanned"] += row.get("pages_scanned", 0)
    stats["priority_pages_scanned_total"] += row.get("priority_pages_scanned", 0)
    stats["sitemap_urls_examined_total"] += row.get("sitemap_urls_examined", 0)
    stats["total_crawl_seconds"] += row.get("crawl_ms", 0) / 1000
    stats["retries_used_total"] += row.get("retries_used", 0)
    status = str(row.get("status", "error") or "error")
    tier = str(row.get("tier", "tier_c") or "tier_c")
    if status in {"ok", "no_contact", "error"}:
        stats[status] += 1
    else:
        stats["error"] += 1
    if tier in {"tier_a", "tier_b", "tier_c"}:
        stats[tier] += 1
    else:
        stats["tier_c"] += 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract emails and social handles from discovered targets.")
    parser.add_argument("--input", type=Path, default=Path("lead-scraper/data/targets.txt"), help="Path to targets file.")
    parser.add_argument(
        "--targets-csv",
        type=Path,
        default=Path("lead-scraper/data/targets.csv"),
        help="Path to scored discovery CSV for metadata join.",
    )
    parser.add_argument("--output-jsonl", type=Path, default=Path("lead-scraper/data/results.jsonl"), help="Output JSONL file.")
    parser.add_argument("--output-csv", type=Path, default=Path("lead-scraper/data/results.csv"), help="Output CSV file.")
    parser.add_argument(
        "--progress-file",
        type=Path,
        default=Path("lead-scraper/data/progress.json"),
        help="Progress JSON file for live UI status.",
    )
    parser.add_argument("--workers", type=int, default=5, help="Concurrent domains to process.")
    parser.add_argument("--batch-size", type=int, default=5000, help="Queue claim chunk size.")
    parser.add_argument("--per-domain-concurrency", type=int, default=1, help="Concurrent workers per domain.")
    parser.add_argument("--retry-budget-by-domain", type=int, default=3, help="Max retry budget per domain.")
    parser.add_argument(
        "--queue-db",
        type=Path,
        default=Path("lead-scraper/data/extract_queue.sqlite"),
        help="SQLite queue state file.",
    )
    parser.add_argument("--fresh-queue", action="store_true", help="Clear queue state before seeding targets.")
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
    target_records = read_target_records(args.input, args.targets_csv)
    if not target_records:
        raise SystemExit("No targets found in input file.")

    total = len(target_records)
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
        "priority_pages_scanned_total": 0,
        "sitemap_urls_examined_total": 0,
        "total_crawl_seconds": 0,
        "retries_used_total": 0,
        "elapsed_minutes": 0.0,
    }
    rows: list[dict[str, Any]] = []
    mx_cache = load_mx_cache(args.mx_cache_file) if args.mx_validation else {}
    queue = QueueStore(args.queue_db)
    try:
        if args.fresh_queue:
            queue.clear()
        queue.upsert_targets(target_records)
        queue.reset_stale_processing()

        resumed_rows = queue.fetch_final_rows()
        for row in resumed_rows:
            apply_row_stats(stats, row)
        run_started = time.perf_counter()

        per_domain_cap = max(1, args.per_domain_concurrency)
        domain_semaphores: dict[str, threading.BoundedSemaphore] = {}
        domain_sem_lock = threading.Lock()

        def get_domain_sem(domain: str) -> threading.BoundedSemaphore:
            with domain_sem_lock:
                sem = domain_semaphores.get(domain)
                if sem is None:
                    sem = threading.BoundedSemaphore(per_domain_cap)
                    domain_semaphores[domain] = sem
                return sem

        while True:
            claimed = queue.claim_batch(max(1, args.batch_size), max(1, args.retry_budget_by_domain))
            if not claimed:
                break

            def run_item(item: dict[str, Any]) -> dict[str, Any]:
                domain = str(item.get("domain", ""))
                sem = get_domain_sem(domain)
                with sem:
                    meta = {
                        "discovery_quality_score": int(item.get("discovery_quality_score", 0) or 0),
                        "is_healthy": bool(int(item.get("is_healthy", 0) or 0)),
                        "quality_flags": str(item.get("quality_flags", "") or ""),
                        "platform_detected": str(item.get("platform_detected", "unknown") or "unknown"),
                    }
                    return process_domain(
                        url=str(item["url"]),
                        target_meta=meta,
                        max_pages=max(1, args.max_pages),
                        timeout=max(5, args.timeout),
                        min_delay=max(0.0, args.min_delay),
                        max_delay=max(args.min_delay, args.max_delay),
                        early_stop_score=max(60, min(100, args.early_stop_score)),
                        mx_enabled=args.mx_validation,
                        mx_cache=mx_cache,
                    )

            with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
                future_map = {pool.submit(run_item, item): item for item in claimed}
                for fut in as_completed(future_map):
                    item = future_map[fut]
                    item_id = int(item["id"])
                    domain = str(item.get("domain", ""))
                    try:
                        row = fut.result()
                    except Exception as exc:
                        row = {
                            "url": item.get("url", ""),
                            "domain": domain,
                            "status": "error",
                            "tier": "tier_c",
                            "error": f"exception:{type(exc).__name__}",
                            "email_all": [],
                            "pages_scanned": 0,
                            "priority_pages_scanned": 0,
                            "sitemap_urls_examined": 0,
                            "crawl_ms": 0,
                            "retries_used": 0,
                            "platform": "unknown",
                            "email_source": "",
                        }

                    if str(row.get("status", "")) == "error":
                        final_fail = queue.mark_failed(
                            item_id=item_id,
                            domain=domain,
                            error=str(row.get("error", "") or "error"),
                            retry_budget_by_domain=max(1, args.retry_budget_by_domain),
                            row=row,
                        )
                        if final_fail:
                            apply_row_stats(stats, row)
                            print(f"[failed] {row.get('domain', row.get('url', ''))} error={row.get('error', 'error')}")
                    else:
                        queue.mark_completed(item_id, row)
                        apply_row_stats(stats, row)
                        print(
                            f"[done] {row.get('domain', row.get('url', ''))} "
                            f"best={row.get('best_contact_type', '')} "
                            f"source={row.get('email_source', '')} "
                            f"conf={row.get('confidence_score', 0)} "
                            f"tier={row.get('tier', '')}"
                        )

                    stats["elapsed_minutes"] = (time.perf_counter() - run_started) / 60.0
                    queue_counts = queue.counts()
                    all_final_rows = queue.fetch_final_rows()
                    source_rates, platform_rates = summarize_success_rates(all_final_rows)
                    write_progress(
                        args.progress_file,
                        build_progress_payload(
                            stats,
                            total=queue_counts.get("total", total),
                            running=True,
                            queue_counts=queue_counts,
                            success_rate_by_source=source_rates,
                            success_rate_by_platform=platform_rates,
                            fail_reasons_distribution=queue.fail_reasons_distribution(),
                        ),
                    )

        rows = queue.fetch_final_rows()
        rows.sort(key=lambda r: r.get("domain", ""))
        queue_counts = queue.counts()
        source_rates, platform_rates = summarize_success_rates(rows)
        write_progress(
            args.progress_file,
            build_progress_payload(
                stats,
                total=queue_counts.get("total", total),
                running=False,
                queue_counts=queue_counts,
                success_rate_by_source=source_rates,
                success_rate_by_platform=platform_rates,
                fail_reasons_distribution=queue.fail_reasons_distribution(),
            ),
        )
    finally:
        queue.close()

    write_jsonl(args.output_jsonl, rows)
    write_csv(args.output_csv, rows)
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
                "priority_pages_scanned": int(stats["priority_pages_scanned_total"]),
                "sitemap_urls_examined": int(stats["sitemap_urls_examined_total"]),
                "queue_db": str(args.queue_db),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
