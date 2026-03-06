import { type ChildProcessWithoutNullStreams, spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

const REPO_ROOT = process.cwd();
export const LEAD_SCRAPER_DIR = path.join(REPO_ROOT, "lead-scraper");
export const DATA_DIR = path.join(LEAD_SCRAPER_DIR, "data");
export const TARGETS_TXT = path.join(DATA_DIR, "targets.txt");
export const TARGETS_CSV = path.join(DATA_DIR, "targets.csv");
export const RESULTS_CSV = path.join(DATA_DIR, "results.csv");
export const RESULTS_JSONL = path.join(DATA_DIR, "results.jsonl");
export const PROGRESS_JSON = path.join(DATA_DIR, "progress.json");
export const EXTRACT_QUEUE_DB = path.join(DATA_DIR, "extract_queue.sqlite");

function resolvePythonExecutable() {
  if (process.env.LEAD_SCRAPER_PYTHON) {
    return process.env.LEAD_SCRAPER_PYTHON;
  }

  if (process.platform === "win32") {
    const localAppData =
      process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local");
    const candidates = [
      path.join(localAppData, "Programs", "Python", "Python312", "python.exe"),
      path.join(localAppData, "Programs", "Python", "Python311", "python.exe"),
      path.join(localAppData, "Programs", "Python", "Python310", "python.exe"),
      "python.exe",
      "python",
    ];
    for (const candidate of candidates) {
      if (candidate.includes(path.sep)) {
        if (existsSync(candidate)) {
          return candidate;
        }
      } else {
        return candidate;
      }
    }
  }

  return "python";
}

const DEFAULT_PYTHON = resolvePythonExecutable();
let activeExtractorChild: ChildProcessWithoutNullStreams | null = null;

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

function runExtractorPython(args: string[], timeoutMs: number): Promise<ScriptResult> {
  return new Promise((resolve) => {
    const command = `${DEFAULT_PYTHON} ${args.join(" ")}`;
    const child = spawn(DEFAULT_PYTHON, args, {
      cwd: REPO_ROOT,
      windowsHide: true,
      env: process.env,
    });
    activeExtractorChild = child;

    let stdout = "";
    let stderr = "";
    let finished = false;

    const timer = setTimeout(() => {
      if (!finished) {
        child.kill("SIGTERM");
      }
    }, timeoutMs);

    const finish = (payload: ScriptResult) => {
      if (finished) {
        return;
      }
      finished = true;
      clearTimeout(timer);
      activeExtractorChild = null;
      resolve(payload);
    };

    child.stdout.on("data", (chunk: Buffer | string) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk: Buffer | string) => {
      stderr += chunk.toString();
    });
    child.on("error", (err) => {
      finish({
        ok: false,
        code: -1,
        stdout,
        stderr: `${stderr}\n${err.message}`.trim(),
        command,
      });
    });
    child.on("close", (code) => {
      finish({
        ok: code === 0,
        code: code ?? -1,
        stdout,
        stderr,
        command,
      });
    });
  });
}

export function isExtractorRunning() {
  return Boolean(activeExtractorChild);
}

export async function stopExtractor(): Promise<{ ok: boolean; message: string }> {
  const child = activeExtractorChild;
  if (!child) {
    return { ok: true, message: "No extraction process is running." };
  }

  const exited = new Promise<boolean>((resolve) => {
    child.once("close", () => resolve(true));
    setTimeout(() => resolve(false), 5000);
  });

  child.kill("SIGTERM");
  const didExit = await exited;
  if (didExit) {
    return { ok: true, message: "Extraction process stopped." };
  }

  child.kill("SIGKILL");
  return { ok: true, message: "Extraction process force-stopped." };
}

export async function clearExtractionOutputs() {
  await Promise.all([
    rm(RESULTS_CSV, { force: true }),
    rm(RESULTS_JSONL, { force: true }),
    rm(PROGRESS_JSON, { force: true }),
    rm(EXTRACT_QUEUE_DB, { force: true }),
  ]);
}

export async function runDiscovery(opts: {
  queries: string[];
  source: "ddg" | "crt" | "both";
  pages: number;
  delay: number;
  crtKeyword: string;
  crtLimit: number;
  minQualityThreshold: number;
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
    "--min-quality-threshold",
    String(opts.minQualityThreshold),
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
  if (activeExtractorChild) {
    return {
      ok: false,
      code: -1,
      stdout: "",
      stderr: "Extractor is already running.",
      command: "busy",
    };
  }

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
  return runExtractorPython(args, 6 * 60 * 60 * 1000);
}
