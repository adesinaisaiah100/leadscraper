import { NextResponse } from "next/server";
import { clearExtractionOutputs, stopExtractor } from "@/lib/lead-scraper";

export const runtime = "nodejs";

type Body = {
  stopExtraction?: boolean;
  clearExtractionData?: boolean;
};

export async function POST(req: Request) {
  let body: Body = {};
  try {
    body = (await req.json()) as Body;
  } catch {
    body = {};
  }

  const stopExtraction = body.stopExtraction !== false;
  const clearExtractionData = body.clearExtractionData !== false;

  const actions: string[] = [];
  if (stopExtraction) {
    const stopped = await stopExtractor();
    actions.push(stopped.message);
  }
  if (clearExtractionData) {
    await clearExtractionOutputs();
    actions.push("Cleared extraction outputs (results, jsonl, progress).");
  }

  return NextResponse.json({
    ok: true,
    actions,
  });
}
