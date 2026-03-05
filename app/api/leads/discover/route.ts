import { NextResponse } from "next/server";
import { runDiscovery } from "@/lib/lead-scraper";

export const runtime = "nodejs";

type Body = {
  queries?: string[];
  source?: "ddg" | "crt" | "both";
  pages?: number;
  delay?: number;
  crtKeyword?: string;
  crtLimit?: number;
};

export async function POST(req: Request) {
  let body: Body = {};
  try {
    body = (await req.json()) as Body;
  } catch {
    return NextResponse.json({ ok: false, error: "Invalid JSON body." }, { status: 400 });
  }

  const queries = (body.queries || []).map((q) => q.trim()).filter(Boolean);
  if (queries.length === 0 && body.source !== "crt") {
    return NextResponse.json(
      { ok: false, error: "Provide at least one query unless source is crt." },
      { status: 400 },
    );
  }

  const source = body.source || "ddg";
  const pages = Math.min(10, Math.max(1, body.pages || 2));
  const delay = Math.min(15, Math.max(0, body.delay || 2));
  const crtKeyword = (body.crtKeyword || "").trim();
  const crtLimit = Math.min(20000, Math.max(100, body.crtLimit || 3000));

  const result = await runDiscovery({ queries, source, pages, delay, crtKeyword, crtLimit });
  return NextResponse.json(
    {
      ok: result.ok,
      source,
      command: result.command,
      code: result.code,
      stdout: result.stdout,
      stderr: result.stderr,
    },
    { status: result.ok ? 200 : 500 },
  );
}
