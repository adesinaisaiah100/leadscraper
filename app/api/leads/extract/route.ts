import { NextResponse } from "next/server";
import { runExtractor } from "@/lib/lead-scraper";

export const runtime = "nodejs";

type Body = {
  workers?: number;
  maxPages?: number;
  timeout?: number;
  minDelay?: number;
  maxDelay?: number;
  earlyStopScore?: number;
  mxValidation?: boolean;
};

export async function POST(req: Request) {
  let body: Body = {};
  try {
    body = (await req.json()) as Body;
  } catch {
    return NextResponse.json({ ok: false, error: "Invalid JSON body." }, { status: 400 });
  }

  const workers = Math.min(20, Math.max(1, body.workers || 5));
  const maxPages = Math.min(10, Math.max(1, body.maxPages || 5));
  const timeout = Math.min(60, Math.max(5, body.timeout || 15));
  const minDelay = Math.min(10, Math.max(0, body.minDelay ?? 0.7));
  const maxDelay = Math.min(20, Math.max(minDelay, body.maxDelay ?? 1.8));
  const earlyStopScore = Math.min(100, Math.max(60, body.earlyStopScore || 95));
  const mxValidation = Boolean(body.mxValidation);

  const result = await runExtractor({
    workers,
    maxPages,
    timeout,
    minDelay,
    maxDelay,
    earlyStopScore,
    mxValidation,
  });
  return NextResponse.json(
    {
      ok: result.ok,
      command: result.command,
      code: result.code,
      stdout: result.stdout,
      stderr: result.stderr,
    },
    { status: result.ok ? 200 : 500 },
  );
}
