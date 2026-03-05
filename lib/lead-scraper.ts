import { spawn } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const REPO_ROOT = process.cwd();
export const LEAD_SCRAPER_DIR = path.join(REPO_ROOT, "lead-scraper");
export const DATA_DIR = path.join(LEAD_SCRAPER_DIR, "data");
export const TARGETS_TXT = path.join(DATA_DIR, "targets.txt");
export const TARGETS_CSV = path.join(DATA_DIR, "targets.csv");
export const RESULTS_CSV = path.join(DATA_DIR, "results.csv");
export const RESULTS_JSONL = path.join(DATA_DIR, "results.jsonl");
export const PROGRESS_JSON = path.join(DATA_DIR, "progress.json");

const DEFAULT_PYTHON = process.env.LEAD_SCRAPER_PYTHON || "python";

export type ScriptResult = {
  ok: boolean;
  code: number;
  stdout: string;
  stderr: string;
  command: string;
};

export async function ensureDataDir() {
  await mkdir(DATA_DIR, { recursive: true });
}

export async function writeRuntimeQueries(queries: string[]) {
  await ensureDataDir();
  const queryPath = path.join(DATA_DIR, "runtime-queries.txt");
  const payload = queries.map((q) => q.trim()).filter(Boolean).join("\n");
  await writeFile(queryPath, `${payload}\n`, "utf8");
  return queryPath;
}

function runPython(args: string[], timeoutMs = 10 * 60 * 1000): Promise<ScriptResult> {
  return new Promise((resolve) => {
    const command = `${DEFAULT_PYTHON} ${args.join(" ")}`;
    const child = spawn(DEFAULT_PYTHON, args, {
      cwd: REPO_ROOT,
      windowsHide: true,
      env: process.env,
    });

    let stdout = "";
    let stderr = "";
    let finished = false;

    const timer = setTimeout(() => {
      if (!finished) {
        child.kill("SIGTERM");
      }
    }, timeoutMs);

    child.stdout.on("data", (chunk: Buffer | string) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk: Buffer | string) => {
      stderr += chunk.toString();
    });
    child.on("error", (err) => {
      if (finished) {
        return;
      }
      finished = true;
      clearTimeout(timer);
      resolve({
        ok: false,
        code: -1,
        stdout,
        stderr: `${stderr}\n${err.message}`.trim(),
        command,
      });
    });
    child.on("close", (code) => {
      if (finished) {
        return;
      }
      finished = true;
      clearTimeout(timer);
      resolve({
        ok: code === 0,
        code: code ?? -1,
        stdout,
        stderr,
        command,
      });
    });
  });
}

export async function runDiscovery(opts: {
  queries: string[];
  source: "ddg" | "crt" | "both";
  pages: number;
  delay: number;
  crtKeyword: string;
  crtLimit: number;
}) {
  const queryPath = await writeRuntimeQueries(opts.queries);
  const args = [
    path.join("lead-scraper", "discovery", "discover.py"),
    "--queries-file",
    queryPath,
    "--source",
    opts.source,
    "--pages",
    String(opts.pages),
    "--delay",
    String(opts.delay),
    "--timeout",
    "60",
    "--crt-keyword",
    opts.crtKeyword,
    "--crt-limit",
    String(opts.crtLimit),
    "--output",
    path.join("lead-scraper", "data", "targets.txt"),
    "--output-csv",
    path.join("lead-scraper", "data", "targets.csv"),
  ];
  return runPython(args);
}

export async function runExtractor(opts: {
  workers: number;
  maxPages: number;
  timeout: number;
  minDelay: number;
  maxDelay: number;
  earlyStopScore: number;
  mxValidation: boolean;
}) {
  await ensureDataDir();
  const args = [
    path.join("lead-scraper", "crawler", "extract_contacts.py"),
    "--input",
    path.join("lead-scraper", "data", "targets.txt"),
    "--output-jsonl",
    path.join("lead-scraper", "data", "results.jsonl"),
    "--output-csv",
    path.join("lead-scraper", "data", "results.csv"),
    "--progress-file",
    path.join("lead-scraper", "data", "progress.json"),
    "--workers",
    String(opts.workers),
    "--max-pages",
    String(opts.maxPages),
    "--timeout",
    String(opts.timeout),
    "--min-delay",
    String(opts.minDelay),
    "--max-delay",
    String(opts.maxDelay),
    "--early-stop-score",
    String(opts.earlyStopScore),
  ];
  if (opts.mxValidation) {
    args.push("--mx-validation");
  }
  return runPython(args, 6 * 60 * 60 * 1000);
}
