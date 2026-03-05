#!/usr/bin/env python3
"""Tool 1: zero-cost lead discovery using DDG static HTML + optional crt.sh."""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
import urllib.parse
from pathlib import Path
from typing import Iterable

import requests
from bs4 import BeautifulSoup

DDG_HTML_URL = "https://html.duckduckgo.com/html/"
CRT_SH_URL = "https://crt.sh/"
BACKOFF_STEPS = (1, 2, 4)
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)


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


def decode_ddg_redirect(url: str) -> str:
    if "uddg=" not in url:
        return url
    query = urllib.parse.urlparse(url).query
    params = urllib.parse.parse_qs(query)
    target = params.get("uddg", [url])[0]
    return urllib.parse.unquote(target)


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
    if last_err:
        print(f"[http] {method} {url} failed after retries: {last_err}")
    return None


def extract_ddg_links(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[str] = []

    selectors = [
        "a.result__a",
        "a[data-testid='result-title-a']",
        ".result a[href]",
        ".links_main a[href]",
    ]
    for selector in selectors:
        for link in soup.select(selector):
            href = link.get("href")
            if href:
                candidates.append(href)

    # Fallback parsing: include any likely outbound link.
    if not candidates:
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if "uddg=" in href or href.startswith(("http://", "https://", "//")):
                candidates.append(href)

    out: list[str] = []
    for href in candidates:
        actual_url = decode_ddg_redirect(href)
        clean = normalize_url(actual_url)
        if clean and "duckduckgo.com" not in clean:
            out.append(clean)
    return out


def scrape_ddg_query(
    session: requests.Session,
    query: str,
    pages: int,
    delay_seconds: float,
    timeout_seconds: int,
) -> list[str]:
    urls: list[str] = []

    for page_index in range(pages):
        # DDG static HTML supports offset through "s".
        offset = page_index * 30
        payload = {"q": query, "s": str(offset)}

        response = request_with_retries(
            session=session,
            method="POST",
            url=DDG_HTML_URL,
            data=payload,
            timeout_seconds=timeout_seconds,
        )
        if not response or response.status_code != 200:
            break

        extracted = extract_ddg_links(response.text)
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


def write_outputs(urls: list[str], output_txt: Path, output_csv: Path) -> None:
    output_txt.parent.mkdir(parents=True, exist_ok=True)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    output_txt.write_text("\n".join(urls) + ("\n" if urls else ""), encoding="utf-8")

    with output_csv.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(["url"])
        for url in urls:
            writer.writerow([url])


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
        description="Discover e-commerce/logistics target URLs using DDG dorks and optional crt.sh."
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
        choices=["ddg", "crt", "both"],
        default="ddg",
        help="Discovery source to use.",
    )
    parser.add_argument("--pages", type=int, default=2, help="DDG pages per query.")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between DDG page requests in seconds.")
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    queries = load_queries(args.query, args.queries_file)

    if args.source in {"ddg", "both"} and not queries:
        raise SystemExit("At least one --query (or --queries-file) is required for ddg source.")

    session = requests.Session()
    session.headers.update({"User-Agent": DEFAULT_UA})

    discovered: list[str] = []

    if args.source in {"ddg", "both"}:
        for query in queries:
            print(f"[ddg] query: {query}")
            results = scrape_ddg_query(
                session=session,
                query=query,
                pages=max(1, args.pages),
                delay_seconds=max(0.0, args.delay),
                timeout_seconds=max(5, args.timeout),
            )
            print(f"[ddg] found: {len(results)}")
            discovered.extend(results)

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
    write_outputs(final_urls, args.output, args.output_csv)
    print(json.dumps({"saved": len(final_urls), "output": str(args.output), "output_csv": str(args.output_csv)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
