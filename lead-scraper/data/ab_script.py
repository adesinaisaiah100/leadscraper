import sys, csv, requests
sys.path.insert(0, './lead-scraper/discovery')
from discover import score_target

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
})
urls = [line.strip() for line in open('lead-scraper/data/ab_urls.txt') if line.strip()]

results = []
for idx, url in enumerate(urls):
    try:
        assessment = score_target(session, url, 10)
        results.append(assessment)
        print(f'{idx}/{len(urls)}: {url} -> {assessment.target_quality_score}')
    except Exception as e:
        print(f'Error {url}: {e}')

with open('lead-scraper/data/ab_discovery.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['url', 'domain', 'target_quality_score', 'quality_flags', 'is_healthy'])
    for r in results:
        w.writerow([r.url, r.domain, r.target_quality_score, '|'.join(r.quality_flags), r.is_healthy])
