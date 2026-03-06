import { readFile } from "node:fs/promises";
import { NextResponse } from "next/server";
import { RESULTS_CSV } from "@/lib/lead-scraper";

export const runtime = "nodejs";

type LeadRow = {
  domain: string;
  url: string;
  best_contact_type: string;
  best_contact_value: string;
  email_primary: string;
  email_source: string;
  platform: string;
  confidence_score: number;
  contact_confidence_score: number;
  discovery_quality_score: number;
  lead_score_v2: number;
  lead_score: number;
  status: string;
  tier: string;
  is_healthy: boolean;
  quality_gate_pass: boolean;
  pages_scanned: number;
  socials_count: number;
};

function parseCsvLine(line: string): string[] {
  const values: string[] = [];
  let current = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (ch === '"') {
      const next = line[i + 1];
      if (inQuotes && next === '"') {
        current += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (ch === "," && !inQuotes) {
      values.push(current);
      current = "";
      continue;
    }
    current += ch;
  }
  values.push(current);
  return values;
}

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const platform = (searchParams.get("platform") || "all").toLowerCase();
  const status = (searchParams.get("status") || "all").toLowerCase();
  const minScore = Number(searchParams.get("minScore") || "0");
  const minDiscoveryQuality = Number(searchParams.get("minDiscoveryQuality") || "0");
  const contactSource = (searchParams.get("contactSource") || "all").toLowerCase();
  const healthyOnly = (searchParams.get("healthyOnly") || "true") === "true";
  const limit = Math.min(200, Math.max(5, Number(searchParams.get("limit") || "25")));
  const hasEmailOnly = (searchParams.get("hasEmailOnly") || "false") === "true";
  const tier = (searchParams.get("tier") || "all").toLowerCase();

  try {
    const raw = await readFile(RESULTS_CSV, "utf8");
    const lines = raw.split(/\r?\n/).filter(Boolean);
    if (lines.length <= 1) {
      return NextResponse.json({ ok: true, rows: [] });
    }

    const headers = parseCsvLine(lines[0]);
    const idx: Record<string, number> = {};
    headers.forEach((h, i) => {
      idx[h] = i;
    });

    const rows: LeadRow[] = [];
    for (const line of lines.slice(1)) {
      const cols = parseCsvLine(line);
      const instagram = cols[idx.instagram] || "";
      const facebook = cols[idx.facebook] || "";
      const linkedin = cols[idx.linkedin] || "";
      const x = cols[idx.x] || "";
      const tiktok = cols[idx.tiktok] || "";
      const pinterest = cols[idx.pinterest] || "";
      const socialsCount = [instagram, facebook, linkedin, x, tiktok, pinterest].filter(Boolean).length;

      rows.push({
        domain: cols[idx.domain] || "",
        url: cols[idx.url] || "",
        best_contact_type: (cols[idx.best_contact_type] || "").toLowerCase(),
        best_contact_value: cols[idx.best_contact_value] || "",
        email_primary: cols[idx.email_primary] || "",
        email_source: (cols[idx.email_source] || "").toLowerCase(),
        platform: (cols[idx.platform] || "unknown").toLowerCase(),
        confidence_score: Number(cols[idx.confidence_score] || "0"),
        contact_confidence_score: Number(cols[idx.contact_confidence_score] || cols[idx.confidence_score] || "0"),
        discovery_quality_score: Number(cols[idx.discovery_quality_score] || "0"),
        lead_score_v2: Number(cols[idx.lead_score_v2] || cols[idx.lead_score] || "0"),
        lead_score: Number(cols[idx.lead_score] || "0"),
        status: (cols[idx.status] || "").toLowerCase(),
        tier: (cols[idx.tier] || "").toLowerCase(),
        is_healthy: (cols[idx.is_healthy] || "").toLowerCase() === "true",
        quality_gate_pass: (cols[idx.quality_gate_pass] || "").toLowerCase() !== "false",
        pages_scanned: Number(cols[idx.pages_scanned] || "0"),
        socials_count: socialsCount,
      });
    }

    const filtered = rows
      .filter((r) => (platform === "all" ? true : r.platform === platform))
      .filter((r) => (status === "all" ? true : r.status === status))
      .filter((r) => (tier === "all" ? true : r.tier === tier))
      .filter((r) => r.lead_score_v2 >= minScore)
      .filter((r) => r.discovery_quality_score >= minDiscoveryQuality)
      .filter((r) => (healthyOnly ? r.is_healthy && r.quality_gate_pass : true))
      .filter((r) => (contactSource === "all" ? true : r.email_source === contactSource))
      .filter((r) => (hasEmailOnly ? Boolean(r.email_primary) : true))
      .sort((a, b) => b.lead_score_v2 - a.lead_score_v2 || b.contact_confidence_score - a.contact_confidence_score)
      .slice(0, limit);

    return NextResponse.json({ ok: true, rows: filtered });
  } catch {
    return NextResponse.json({ ok: true, rows: [] });
  }
}
