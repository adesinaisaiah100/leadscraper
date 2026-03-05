import { readFile } from "node:fs/promises";
import { NextResponse } from "next/server";
import { PROGRESS_JSON } from "@/lib/lead-scraper";

export const runtime = "nodejs";

const EMPTY_PROGRESS = {
  running: false,
  domains_total: 0,
  total: 0,
  domains_processed: 0,
  processed: 0,
  remaining: 0,
  emails_found: 0,
  ok: 0,
  no_contact: 0,
  error: 0,
  tier_a: 0,
  tier_b: 0,
  tier_c: 0,
  pct_tier_a: 0,
  pct_tier_b: 0,
  pct_tier_c: 0,
  avg_pages_scanned: 0,
  avg_seconds_per_domain: 0,
  retries_used_total: 0,
  updated_at: null,
};

export async function GET() {
  try {
    const raw = await readFile(PROGRESS_JSON, "utf8");
    const parsed = JSON.parse(raw);
    return NextResponse.json({ ok: true, progress: { ...EMPTY_PROGRESS, ...parsed } });
  } catch {
    return NextResponse.json({ ok: true, progress: EMPTY_PROGRESS });
  }
}
