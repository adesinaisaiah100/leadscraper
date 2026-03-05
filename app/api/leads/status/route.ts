import { readFile, stat } from "node:fs/promises";
import { NextResponse } from "next/server";
import { RESULTS_CSV, TARGETS_CSV } from "@/lib/lead-scraper";

export const runtime = "nodejs";

async function exists(filePath: string) {
  try {
    await stat(filePath);
    return true;
  } catch {
    return false;
  }
}

type FileSummary = {
  ready: boolean;
  path: string;
  sizeBytes: number;
  sizeLabel: string;
  count: number;
  lastModified: string | null;
};

function toSizeLabel(sizeBytes: number) {
  if (sizeBytes < 1024) {
    return `${sizeBytes} B`;
  }
  if (sizeBytes < 1024 * 1024) {
    return `${(sizeBytes / 1024).toFixed(1)} KB`;
  }
  return `${(sizeBytes / (1024 * 1024)).toFixed(2)} MB`;
}

async function summarizeCsv(filePath: string): Promise<FileSummary> {
  const ready = await exists(filePath);
  if (!ready) {
    return {
      ready: false,
      path: filePath,
      sizeBytes: 0,
      sizeLabel: "0 B",
      count: 0,
      lastModified: null,
    };
  }

  const [fileStat, fileBuffer] = await Promise.all([stat(filePath), readFile(filePath)]);
  const text = fileBuffer.toString("utf8").trim();
  const lines = text ? text.split(/\r?\n/) : [];
  const count = Math.max(0, lines.length - 1);

  return {
    ready: true,
    path: filePath,
    sizeBytes: fileStat.size,
    sizeLabel: toSizeLabel(fileStat.size),
    count,
    lastModified: fileStat.mtime.toISOString(),
  };
}

export async function GET() {
  const [targets, results] = await Promise.all([summarizeCsv(TARGETS_CSV), summarizeCsv(RESULTS_CSV)]);
  return NextResponse.json({
    ok: true,
    targetsReady: targets.ready,
    resultsReady: results.ready,
    history: [
      { key: "targets", label: "Discovery Targets", ...targets },
      { key: "results", label: "Extracted Results", ...results },
    ],
  });
}
