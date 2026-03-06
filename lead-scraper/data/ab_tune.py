import csv

def is_quality_gate_blocked(is_healthy: bool, quality_flags: list[str]) -> bool:
    if not is_healthy:
        return True
    bad_flags = {"parked_page", "placeholder_page", "non_html_response"}
    return any(flag in bad_flags for flag in quality_flags)

def email_local_part(email: str) -> str:
    if not email or "@" not in email:
        return ""
    return email.split("@")[0].lower()

RISKY_EMAIL_LOCALS = {
    "info", "contact", "support", "hello", "sales", "admin", "webmaster", 
    "billing", "postmaster", "office", "marketing", "enquiries", "pr",
    "help", "service", "press"
}

def compute(row, w_disc, w_cont, p_risky, p_guess, p_gate):
    disc = int(row.get('target_quality_score', 0))
    cont = int(row.get('confidence_score', 0))
    email = row.get('email_primary', '')
    source = row.get('email_source', '')
    flags = row.get('quality_flags', '').split('|')
    is_healthy = str(row.get('is_healthy', '')).lower() == 'true'
    
    blocked = is_quality_gate_blocked(is_healthy, flags)
    
    score = round((w_disc * disc) + (w_cont * cont))
    if email:
        if email_local_part(email) in RISKY_EMAIL_LOCALS:
            score -= p_risky
        if source == "domain_guess":
            score -= p_guess
    if blocked:
        score -= p_gate
        
    return max(0, min(100, score))


with open('lead-scraper/data/benchmark/current_results.csv', 'r', encoding='utf-8') as f:
    extr = list(csv.DictReader(f))

with open('lead-scraper/data/ab_discovery.csv', 'r', encoding='utf-8') as f:
    disc = list(csv.DictReader(f))

disc_map = {d['url']: d for d in disc}

merged = []
for r in extr:
    d = disc_map.get(r['url'], {})
    r.update(d)
    merged.append(r)

def evaluate(w_disc, w_cont, p_risky, p_guess, p_gate):
    scores = []
    for r in merged:
        v2 = compute(r, w_disc, w_cont, p_risky, p_guess, p_gate)
        # Old lead score:
        v1 = int(r.get('lead_score', 0))
        scores.append({
            'domain': r['domain'],
            'email': r['email_primary'],
            'v1': v1,
            'v2': v2
        })
    
    scores_v1 = sorted(scores, key=lambda x: x['v1'], reverse=True)
    scores_v2 = sorted(scores, key=lambda x: x['v2'], reverse=True)
    
    # We want top 10 leads to have non-empty emails, and prefer non-risky
    def metric(top_list):
        has_email = sum(1 for x in top_list if x['email'])
        non_risky = sum(1 for x in top_list if x['email'] and email_local_part(x['email']) not in RISKY_EMAIL_LOCALS)
        return has_email * 2 + non_risky
        
    m1 = metric(scores_v1[:15])
    m2 = metric(scores_v2[:15])
    return m1, m2, scores_v2

print("Running Grid Search on A/B values...")
best_score = -1
best_params = None
best_v2_list = None

for w_disc in [0.3, 0.4, 0.5]:
    for w_cont in [0.5, 0.6, 0.7]:
        if abs(w_disc + w_cont - 1.0) > 0.01: continue
        for p_risky in [5, 8, 12]:
            for p_guess in [5, 10, 15]:
                for p_gate in [20, 30, 40]:
                    m1, m2, v2_list = evaluate(w_disc, w_cont, p_risky, p_guess, p_gate)
                    if m2 > best_score:
                        best_score = m2
                        best_params = (w_disc, w_cont, p_risky, p_guess, p_gate)
                        best_v2_list = v2_list

print(f"Old logic metric (top 15): {evaluate(0.4, 0.6, 8, 10, 30)[0]}")
print(f"Best V2 metric (top 15): {best_score}")
print(f"Best Params: w_disc={best_params[0]}, w_cont={best_params[1]}, p_risky={best_params[2]}, p_guess={best_params[3]}, p_gate={best_params[4]}")

print("\nTop 5 with V1 logic:")
for x in sorted(merged, key=lambda x: int(x.get('lead_score', 0)), reverse=True)[:5]:
    print(f"  {x['domain']} | {x['email_primary']} | V1: {x['lead_score']}")

print("\nTop 5 with Best V2 logic:")
for idx, x in enumerate(best_v2_list[:5]):
    print(f"  {x['domain']} | {x['email']} | V2: {x['v2']}")

