import { readFile } from "node:fs/promises";
import { NextResponse } from "next/server";
import { RESULTS_CSV, TARGETS_CSV } from "@/lib/lead-scraper";

export const runtime = "nodejs";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const file = searchParams.get("file");

  const selected = file === "targets" ? TARGETS_CSV : file === "results" ? RESULTS_CSV : null;
  if (!selected) {
    return NextResponse.json({ ok: false, error: "Use ?file=targets or ?file=results" }, { status: 400 });
  }

  try {
    const contents = await readFile(selected);
    const filename = file === "targets" ? "targets.csv" : "results.csv";
    return new NextResponse(contents, {
      status: 200,
      headers: {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": `attachment; filename="${filename}"`,
      },
    });
  } catch {
    return NextResponse.json({ ok: false, error: "File not found. Run scraper first." }, { status: 404 });
  }
}
