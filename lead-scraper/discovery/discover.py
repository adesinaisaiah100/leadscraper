#!/usr/bin/env python3
"""Tool 1: zero-cost lead discovery using Brave, Bing RSS, and optional crt.sh."""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests
from bs4 import BeautifulSoup

BRAVE_SEARCH_URL = "https://search.brave.com/search"
BING_SEARCH_URL = "https://www.bing.com/search"
CRT_SH_URL = "https://crt.sh/"
BACKOFF_STEPS = (1, 2, 4)
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)
SOCIAL_HOST_MARKERS = (
    "instagram.com",
    "facebook.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "tiktok.com",
)
PARKED_MARKERS = (
    "domain for sale",
    "buy this domain",
    "this domain may be for sale",
    "is parked",
    "parkingcrew",
    "sedo",
    "hugedomains",
    "cashparking",
)
PLACEHOLDER_MARKERS = (
    "coming soon",
    "under construction",
    "default web site page",
    "test page",
    "lorem ipsum",
)
INTENT_MARKERS = (
    "/products",
    "cart",
    "checkout",
    "add to cart",
)
SEARCH_ENGINE_BLOCKLIST = (
    "search.brave.com",
    "brave.com",
    "bing.com",
    "microsoft.com",
)


@dataclass
class TargetAssessment:
    url: str
    domain: str
    platform_detected: str
    target_quality_score: int
    quality_flags: list[str]
    is_healthy: bool


def clamp_int(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def normalize_url(raw: str) -> str | None:
    raw = (raw or "").strip()
    if not raw:
        return None

    if raw.startswith("//"):
        raw = f"https:{raw}"
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", raw):
        raw = f"https://{raw}"

    try:
        parsed = urllib.parse.urlparse(raw)
    except Exception:
        return None

    if not parsed.netloc:
        return None

    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return f"{parsed.scheme.lower()}://{netloc}"


def request_with_retries(
    session: requests.Session,
    method: str,
    url: str,
    timeout_seconds: int,
    **kwargs,
) -> requests.Response | None:
    last_err: Exception | None = None
    for attempt, backoff in enumerate(BACKOFF_STEPS, start=1):
        try:
            response = session.request(method=method, url=url, timeout=timeout_seconds, **kwargs)
            if response.status_code >= 500:
                raise requests.HTTPError(f"status={response.status_code}")
            return response
        except requests.RequestException as exc:
            last_err = exc
            if attempt < len(BACKOFF_STEPS):
                time.sleep(backoff)
        except KeyboardInterrupt:
            raise
        except Exception as exc:  # pragma: no cover - defensive network guard
            last_err = exc
            if attempt < len(BACKOFF_STEPS):
                time.sleep(backoff)
    if last_err:
        print(f"[http] {method} {url} failed after retries: {last_err}")
    return None


def normalize_result_url(raw: str) -> str | None:
    clean = normalize_url(raw)
    if not clean:
        return None

    parsed = urllib.parse.urlparse(clean)
    host = parsed.netloc.lower()
    if any(marker in host for marker in SEARCH_ENGINE_BLOCKLIST):
        return None
    return clean


def extract_brave_links(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[str] = []

    selectors = [
        "a[data-test='result-title-a']",
        "a.snippet-title[href]",
        "div[data-type='web'] a[href]",
        "main a[href]",
    ]
    for selector in selectors:
        for link in soup.select(selector):
            href = link.get("href")
            if href:
                candidates.append(href)

    if not candidates:
        for link in soup.find_all("a", href=True):
            candidates.append(link.get("href", ""))

    out: list[str] = []
    for href in candidates:
        if href.startswith("/") or href.startswith("#") or href.startswith("javascript:"):
            continue
        clean = normalize_result_url(href)
        if clean:
            out.append(clean)
    return out


def extract_bing_rss_links(xml_text: str) -> list[str]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    out: list[str] = []
    for item in root.findall("./channel/item"):
        link_text = (item.findtext("link") or "").strip()
        clean = normalize_result_url(link_text)
        if clean:
            out.append(clean)
    return out


def scrape_brave_query(
    session: requests.Session,
    query: str,
    pages: int,
    delay_seconds: float,
    timeout_seconds: int,
) -> list[str]:
    urls: list[str] = []

    for page_index in range(pages):
        response = request_with_retries(
            session=session,
            method="GET",
            url=BRAVE_SEARCH_URL,
            params={
                "q": query,
                "source": "web",
                "offset": str(page_index * 20),
            },
            timeout_seconds=timeout_seconds,
        )
        if not response:
            break
        if response.status_code == 429:
            print(f"[brave] rate limited for query: {query}")
            break
        if response.status_code != 200:
            break

        extracted = extract_brave_links(response.text)
        if not extracted:
            break

        urls.extend(extracted)

        if page_index < pages - 1:
            time.sleep(delay_seconds)

    return urls


def scrape_bing_query(
    session: requests.Session,
    query: str,
    pages: int,
    delay_seconds: float,
    timeout_seconds: int,
) -> list[str]:
    urls: list[str] = []

    for page_index in range(pages):
        response = request_with_retries(
            session=session,
            method="GET",
            url=BING_SEARCH_URL,
            params={
                "q": query,
                "format": "rss",
                "setlang": "en",
                "first": str((page_index * 10) + 1),
            },
            timeout_seconds=timeout_seconds,
        )
        if not response or response.status_code != 200:
            break

        extracted = extract_bing_rss_links(response.text)
        if not extracted:
            break

        urls.extend(extracted)

        if page_index < pages - 1:
            time.sleep(delay_seconds)

    return urls


def fetch_crt_myshopify(
    session: requests.Session,
    keyword: str | None,
    timeout_seconds: int,
    limit: int,
) -> list[str]:
    keyword = (keyword or "").strip().lower()

    # Query broad myshopify certs then filter client-side when keyword is used.
    params = {"q": "%.myshopify.com", "output": "json"}
    response = request_with_retries(
        session=session,
        method="GET",
        url=CRT_SH_URL,
        params=params,
        timeout_seconds=timeout_seconds,
    )
    if not response:
        print("[crt] request error after retries")
        return []

    if response.status_code != 200:
        print(f"[crt] non-200 response: {response.status_code}")
        return []

    try:
        rows = response.json()
    except Exception:
        return []

    found: list[str] = []
    for row in rows:
        names = row.get("name_value", "")
        for item in str(names).splitlines():
            host = item.strip().lower()
            if "*" in host or not host.endswith(".myshopify.com"):
                continue
            if keyword and keyword not in host:
                continue
            clean = normalize_url(host)
            if clean:
                found.append(clean)
                if len(found) >= limit:
                    return found
    return found


def detect_platform(url: str, html_lower: str) -> str:
    u = url.lower()
    if "cdn.shopify.com" in html_lower or "shopify.theme" in html_lower or "myshopify.com" in u:
        return "shopify"
    if "woocommerce" in html_lower or "wp-content/plugins/woocommerce" in html_lower:
        return "woocommerce"
    if "mage/cookies.js" in html_lower or "magento" in html_lower:
        return "magento"
    if "cdn11.bigcommerce.com" in html_lower or "bigcommerce" in html_lower:
        return "bigcommerce"
    return "unknown"


def score_target(session: requests.Session, url: str, timeout_seconds: int) -> TargetAssessment:
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    flags: list[str] = []
    score = 0
    is_healthy = False
    platform_detected = "unknown"

    response = request_with_retries(
        session=session,
        method="GET",
        url=url,
        timeout_seconds=timeout_seconds,
        allow_redirects=True,
    )
    if not response:
        flags.append("fetch_failed")
        return TargetAssessment(
            url=url,
            domain=domain,
            platform_detected=platform_detected,
            target_quality_score=score,
            quality_flags=flags,
            is_healthy=False,
        )

    status_code = response.status_code
    flags.append(f"status_{status_code}")
    body_lower = response.text.lower() if response.text else ""
    content_type = (response.headers.get("content-type", "") or "").lower()
    if "text/html" not in content_type:
        flags.append("non_html_response")
    soup = BeautifulSoup(response.text or "", "html.parser")
    hrefs = [link.get("href", "").lower() for link in soup.find_all("a", href=True)]
    blob = " ".join([body_lower, " ".join(hrefs)])

    is_parked = any(marker in body_lower for marker in PARKED_MARKERS)
    is_placeholder = any(marker in body_lower for marker in PLACEHOLDER_MARKERS)
    if is_parked:
        flags.append("parked_page")
    if is_placeholder:
        flags.append("placeholder_page")

    if status_code == 200 and "text/html" in content_type and not is_parked and not is_placeholder:
        flags.append("healthy_http")
        is_healthy = True
        score += 30

    platform_detected = detect_platform(str(response.url), body_lower)
    if platform_detected != "unknown":
        flags.append(f"platform_{platform_detected}")
        score += 30

    intent_hits = 0
    for marker in INTENT_MARKERS:
        token = marker.lower()
        if token in blob:
            intent_hits += 1
            flags.append(f"intent_{token.replace(' ', '_').replace('/', '')}")
    if intent_hits > 0:
        score += min(25, intent_hits * 8)

    contact_hits = 0
    if "/contact" in blob or "contact us" in blob:
        contact_hits += 1
        flags.append("contact_page")
    if "mailto:" in blob:
        contact_hits += 1
        flags.append("mailto_present")
    social_hits = 0
    for host in SOCIAL_HOST_MARKERS:
        if host in blob:
            social_hits += 1
    if social_hits > 0:
        flags.append("social_links")
        score += min(10, social_hits * 3)
    if contact_hits > 0:
        score += min(15, contact_hits * 8)

    if is_parked:
        score -= 40
    if is_placeholder:
        score -= 20
    if status_code >= 400:
        score -= 30

    return TargetAssessment(
        url=url,
        domain=domain,
        platform_detected=platform_detected,
        target_quality_score=clamp_int(score, 0, 100),
        quality_flags=sorted(set(flags)),
        is_healthy=is_healthy,
    )


def load_queries(cli_queries: list[str], queries_file: Path | None) -> list[str]:
    queries: list[str] = []
    queries.extend(q.strip() for q in cli_queries if q.strip())

    if queries_file and queries_file.exists():
        lines = queries_file.read_text(encoding="utf-8").splitlines()
        queries.extend(line.strip() for line in lines if line.strip() and not line.startswith("#"))

    seen = set()
    ordered: list[str] = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            ordered.append(q)
    return ordered


def write_outputs(
    assessments: list[TargetAssessment],
    output_txt: Path,
    output_csv: Path,
    min_quality_threshold: int,
) -> None:
    output_txt.parent.mkdir(parents=True, exist_ok=True)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    eligible_urls = [
        row.url
        for row in assessments
        if row.is_healthy and row.target_quality_score >= min_quality_threshold
    ]
    output_txt.write_text("\n".join(eligible_urls) + ("\n" if eligible_urls else ""), encoding="utf-8")

    with output_csv.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(
            [
                "url",
                "domain",
                "platform_detected",
                "target_quality_score",
                "quality_flags",
                "is_healthy",
            ]
        )
        for row in assessments:
            writer.writerow(
                [
                    row.url,
                    row.domain,
                    row.platform_detected,
                    row.target_quality_score,
                    "|".join(row.quality_flags),
                    str(row.is_healthy).lower(),
                ]
            )


def unique(items: Iterable[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Discover target URLs using Brave, Bing RSS, and optional crt.sh."
    )
    parser.add_argument(
        "--query",
        action="append",
        default=[],
        help='Search query. Repeat flag for multiple queries. Example: --query \'inurl:myshopify.com "logistics"\'',
    )
    parser.add_argument(
        "--queries-file",
        type=Path,
        default=None,
        help="Path to line-delimited queries file.",
    )
    parser.add_argument(
        "--source",
        choices=["brave", "bing", "crt", "both"],
        default="both",
        help="Discovery source to use.",
    )
    parser.add_argument("--pages", type=int, default=2, help="Search result pages per query for Brave/Bing.")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between Brave/Bing page requests in seconds.")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds.")
    parser.add_argument(
        "--crt-keyword",
        type=str,
        default="",
        help="Optional keyword filter applied to myshopify hostnames from crt.sh.",
    )
    parser.add_argument("--crt-limit", type=int, default=3000, help="Max domains to keep from crt.sh.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("lead-scraper/data/targets.txt"),
        help="Output TXT file of discovered URLs.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("lead-scraper/data/targets.csv"),
        help="Output CSV file of discovered URLs.",
    )
    parser.add_argument(
        "--min-quality-threshold",
        type=int,
        default=50,
        help="Minimum quality score required to include target in TXT extraction input.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    queries = load_queries(args.query, args.queries_file)

    if args.source in {"brave", "bing"} and not queries:
        raise SystemExit("At least one --query (or --queries-file) is required for brave/bing sources.")

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": DEFAULT_UA,
            "Accept-Language": "en-US,en;q=0.9",
        }
    )

    discovered: list[str] = []

    if args.source in {"brave", "both"} and queries:
        for query in queries:
            print(f"[brave] query: {query}")
            results = scrape_brave_query(
                session=session,
                query=query,
                pages=max(1, args.pages),
                delay_seconds=max(0.0, args.delay),
                timeout_seconds=max(5, args.timeout),
            )
            print(f"[brave] found: {len(results)}")
            discovered.extend(results)

    if args.source in {"bing", "both"} and queries:
        for query in queries:
            print(f"[bing] query: {query}")
            results = scrape_bing_query(
                session=session,
                query=query,
                pages=max(1, args.pages),
                delay_seconds=max(0.0, args.delay),
                timeout_seconds=max(5, args.timeout),
            )
            print(f"[bing] found: {len(results)}")
            discovered.extend(results)

    if args.source == "both" and not queries:
        print("[search] no queries provided; skipping Brave/Bing and using CRT only")

    if args.source in {"crt", "both"}:
        print(f"[crt] fetching myshopify certs (keyword={args.crt_keyword or 'none'})")
        crt_results = fetch_crt_myshopify(
            session=session,
            keyword=args.crt_keyword,
            timeout_seconds=max(5, args.timeout),
            limit=max(1, args.crt_limit),
        )
        print(f"[crt] found: {len(crt_results)}")
        discovered.extend(crt_results)

    final_urls = unique(discovered)
    print(f"[quality] validating homepages: {len(final_urls)}")
    assessments: list[TargetAssessment] = []
    for idx, url in enumerate(final_urls, start=1):
        if idx % 50 == 0:
            print(f"[quality] scored {idx}/{len(final_urls)}")
        assessments.append(score_target(session=session, url=url, timeout_seconds=max(5, args.timeout)))

    min_quality_threshold = clamp_int(args.min_quality_threshold, 0, 100)
    write_outputs(assessments, args.output, args.output_csv, min_quality_threshold=min_quality_threshold)
    kept = sum(1 for row in assessments if row.is_healthy and row.target_quality_score >= min_quality_threshold)
    print(
        json.dumps(
            {
                "saved_csv": len(assessments),
                "saved_txt": kept,
                "min_quality_threshold": min_quality_threshold,
                "output": str(args.output),
                "output_csv": str(args.output_csv),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
