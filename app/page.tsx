"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

const DEFAULT_QUERIES = [
  'inurl:myshopify.com "logistics"',
  '"powered by shopify" "logistics" -inurl:myshopify.com',
  'inurl:/wp-content/plugins/woocommerce "logistics"',
];

type StatusResponse = {
  ok: boolean;
  targetsReady: boolean;
  resultsReady: boolean;
  history: HistoryRow[];
};

type ProgressResponse = {
  ok: boolean;
  progress: ProgressState;
};

type TopLeadsResponse = {
  ok: boolean;
  rows: TopLeadRow[];
};

type ResetResponse = {
  ok: boolean;
  actions?: string[];
};

type HistoryRow = {
  key: string;
  label: string;
  ready: boolean;
  sizeBytes: number;
  sizeLabel: string;
  count: number;
  lastModified: string | null;
};

type ProgressState = {
  running: boolean;
  domains_total: number;
  total: number;
  domains_processed: number;
  processed: number;
  remaining: number;
  emails_found: number;
  ok: number;
  no_contact: number;
  error: number;
  tier_a: number;
  tier_b: number;
  tier_c: number;
  pct_tier_a: number;
  pct_tier_b: number;
  pct_tier_c: number;
  avg_pages_scanned: number;
  avg_seconds_per_domain: number;
  priority_pages_scanned: number;
  sitemap_urls_examined: number;
  retries_used_total: number;
  queue_pending: number;
  queue_processing: number;
  queue_completed: number;
  queue_failed: number;
  throughput_domains_per_minute: number;
  updated_at: string | null;
};

type TopLeadRow = {
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

export default function Home() {
  const [queriesText, setQueriesText] = useState(DEFAULT_QUERIES.join("\n"));
  const [source, setSource] = useState<"ddg" | "crt" | "both">("ddg");
  const [pages, setPages] = useState(2);
  const [workers, setWorkers] = useState(5);
  const [maxPages, setMaxPages] = useState(5);
  const [extractTimeout, setExtractTimeout] = useState(15);
  const [minDelay, setMinDelay] = useState(0.7);
  const [maxDelay, setMaxDelay] = useState(1.8);
  const [earlyStopScore, setEarlyStopScore] = useState(95);
  const [mxValidation, setMxValidation] = useState(false);
  const [crtKeyword, setCrtKeyword] = useState("logistics");
  const [crtLimit, setCrtLimit] = useState(3000);
  const [minQualityThreshold, setMinQualityThreshold] = useState(50);
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [targetsReady, setTargetsReady] = useState(false);
  const [resultsReady, setResultsReady] = useState(false);
  const [historyRows, setHistoryRows] = useState<HistoryRow[]>([]);
  const [topLeads, setTopLeads] = useState<TopLeadRow[]>([]);
  const [leadPlatform, setLeadPlatform] = useState("all");
  const [leadStatus, setLeadStatus] = useState("all");
  const [leadTier, setLeadTier] = useState("all");
  const [leadMinScore, setLeadMinScore] = useState(20);
  const [leadMinDiscoveryQuality, setLeadMinDiscoveryQuality] = useState(50);
  const [leadContactSource, setLeadContactSource] = useState("all");
  const [leadHealthyOnly, setLeadHealthyOnly] = useState(true);
  const [leadLimit, setLeadLimit] = useState(25);
  const [hasEmailOnly, setHasEmailOnly] = useState(true);
  const [progress, setProgress] = useState<ProgressState>({
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
    priority_pages_scanned: 0,
    sitemap_urls_examined: 0,
    retries_used_total: 0,
    queue_pending: 0,
    queue_processing: 0,
    queue_completed: 0,
    queue_failed: 0,
    throughput_domains_per_minute: 0,
    updated_at: null,
  });
  const [logText, setLogText] = useState("Ready.");

  const queries = useMemo(
    () =>
      queriesText
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
    [queriesText],
  );

  async function refreshStatus() {
    try {
      const resp = await fetch("/api/leads/status", { cache: "no-store" });
      const data = (await resp.json()) as StatusResponse;
      if (data.ok) {
        setTargetsReady(data.targetsReady);
        setResultsReady(data.resultsReady);
        setHistoryRows(data.history || []);
      }
    } catch {
      setLogText((prev) => `${prev}\n[status] failed to fetch status`);
    }
  }

  async function refreshProgress() {
    try {
      const resp = await fetch("/api/leads/progress", { cache: "no-store" });
      const data = (await resp.json()) as ProgressResponse;
      if (data.ok) {
        setProgress(data.progress);
      }
    } catch {
      setLogText((prev) => `${prev}\n[progress] failed to fetch progress`);
    }
  }

  const refreshTopLeads = useCallback(async () => {
    try {
      const params = new URLSearchParams({
        platform: leadPlatform,
        status: leadStatus,
        tier: leadTier,
        minScore: String(leadMinScore),
        minDiscoveryQuality: String(leadMinDiscoveryQuality),
        contactSource: String(leadContactSource),
        healthyOnly: String(leadHealthyOnly),
        limit: String(leadLimit),
        hasEmailOnly: String(hasEmailOnly),
      });
      const resp = await fetch(`/api/leads/top?${params.toString()}`, { cache: "no-store" });
      const data = (await resp.json()) as TopLeadsResponse;
      if (data.ok) {
        setTopLeads(data.rows || []);
      }
    } catch {
      setLogText((prev) => `${prev}\n[top-leads] failed to fetch`);
    }
  }, [leadPlatform, leadStatus, leadTier, leadMinScore, leadMinDiscoveryQuality, leadContactSource, leadHealthyOnly, leadLimit, hasEmailOnly]);

  useEffect(() => {
    refreshStatus();
    refreshProgress();
    refreshTopLeads();
  }, [refreshTopLeads]);

  useEffect(() => {
    refreshTopLeads();
  }, [refreshTopLeads]);

  useEffect(() => {
    if (!isExtracting) {
      return;
    }
    const timer = setInterval(() => {
      refreshProgress();
    }, 2000);
    return () => clearInterval(timer);
  }, [isExtracting]);

  async function runDiscovery() {
    setIsDiscovering(true);
    setLogText("[discovery] running...");
    try {
      const resp = await fetch("/api/leads/discover", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          queries,
          source,
          pages,
          delay: 2,
          crtKeyword,
          crtLimit,
          minQualityThreshold,
        }),
      });
      const data = await resp.json();
      const combined = [data.stdout, data.stderr].filter(Boolean).join("\n");
      setLogText(`[discovery] ${data.ok ? "done" : "failed"}\n${combined || "No output."}`);
      await refreshStatus();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setLogText(`[discovery] failed\n${message}`);
    } finally {
      setIsDiscovering(false);
    }
  }

  async function runExtractor() {
    setIsExtracting(true);
    setLogText("[extractor] running...");
    await refreshProgress();
    try {
      const resp = await fetch("/api/leads/extract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workers,
          maxPages,
          timeout: extractTimeout,
          minDelay,
          maxDelay,
          earlyStopScore,
          mxValidation,
        }),
      });
      const data = await resp.json();
      const combined = [data.stdout, data.stderr].filter(Boolean).join("\n");
      setLogText(`[extractor] ${data.ok ? "done" : "failed"}\n${combined || "No output."}`);
      await refreshStatus();
      await refreshProgress();
      await refreshTopLeads();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setLogText(`[extractor] failed\n${message}`);
    } finally {
      setIsExtracting(false);
      await refreshProgress();
      await refreshTopLeads();
    }
  }

  async function stopAndResetExtraction() {
    const confirmed = window.confirm(
      "Stop the current extraction and clear all extraction outputs (Top Leads, results, and progress)?",
    );
    if (!confirmed) {
      return;
    }

    setIsResetting(true);
    try {
      const resp = await fetch("/api/leads/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          stopExtraction: true,
          clearExtractionData: true,
        }),
      });
      const data = (await resp.json()) as ResetResponse;
      setIsExtracting(false);
      await refreshStatus();
      await refreshProgress();
      await refreshTopLeads();
      setLogText(
        `[reset] ${data.ok ? "done" : "failed"}\n${(data.actions || []).join("\n") || "No output."}`,
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setLogText(`[reset] failed\n${message}`);
    } finally {
      setIsResetting(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-[#0f172a] text-slate-300 font-sans selection:bg-indigo-500/30">
      <header className="sticky top-0 z-10 border-b border-white/10 bg-[#0f172a]/80 px-8 py-5 backdrop-blur-md">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white">Lead Scraper Studio</h1>
            <p className="text-sm font-medium text-slate-400 mt-1">Discover, extract, and export high-quality leads</p>
          </div>
          <div className="flex items-center gap-4">
            <button
              className={`flex items-center justify-center rounded-xl px-6 py-3 text-sm font-semibold transition-all ${
                targetsReady ? "bg-[#1e293b] text-white border border-white/10 shadow-sm hover:bg-white/5" : "pointer-events-none bg-white/5 text-slate-500 border border-transparent"
              }`}
              onClick={() => window.open("/api/leads/download?file=targets", "_blank")}
            >
              Export Targets
            </button>
            <button
              className={`flex items-center justify-center rounded-xl px-6 py-3 text-sm font-semibold transition-all ${
                resultsReady ? "bg-indigo-600 text-white shadow-md shadow-indigo-500/20 hover:bg-indigo-500" : "pointer-events-none bg-indigo-600/20 text-indigo-400/50"
              }`}
              onClick={() => window.open("/api/leads/download?file=results", "_blank")}
            >
              Export Results
            </button>
          </div>
        </div>
      </header>

      <main className="flex flex-1 flex-col lg:flex-row gap-8 p-8 max-w-[1600px] mx-auto w-full relative z-0">
        <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-500/5 blur-[120px] pointer-events-none" />
        <div className="absolute bottom-0 left-0 w-96 h-96 bg-cyan-500/5 blur-[120px] pointer-events-none" />

        {/* Left Column: Controls */}
        <div className="flex w-full flex-col gap-8 lg:w-5/12 xl:w-1/3 shrink-0 relative z-10">
          
          {/* Discovery Panel */}
          <section className="rounded-3xl border border-white/5 bg-[#1e293b]/40 backdrop-blur-md p-6 shadow-xl">
            <h2 className="text-lg font-semibold text-white mb-5 flex items-center gap-3">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-500/20 text-sm text-indigo-400">1</span>
              Discovery Configuration
            </h2>
            
            <div className="flex flex-col gap-5 text-sm">
              <label className="flex flex-col gap-2 font-medium text-slate-300">
                Source Mode
                <select
                  className="rounded-xl border border-white/10 bg-[#0f172a] text-white px-4 py-3 outline-none transition-colors focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                  value={source}
                  onChange={(e) => setSource(e.target.value as "ddg" | "crt" | "both")}
                >
                  <option value="ddg">DuckDuckGo Only</option>
                  <option value="crt">CRT Certificate Search Only</option>
                  <option value="both">Combined (DDG + CRT)</option>
                </select>
              </label>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
                <label className="flex flex-col gap-2 font-medium text-slate-300">
                  Pages per Query
                  <input
                    className="rounded-xl border border-white/10 bg-[#0f172a] text-white px-4 py-3 outline-none transition-colors focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                    type="number"
                    min={1}
                    max={10}
                    value={pages}
                    onChange={(e) => setPages(Number(e.target.value) || 2)}
                  />
                </label>
                <label className="flex flex-col gap-2 font-medium text-slate-300">
                  CRT Keyword
                  <input
                    className="rounded-xl border border-white/10 bg-[#0f172a] text-white px-4 py-3 outline-none transition-colors focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 placeholder-slate-600"
                    value={crtKeyword}
                    onChange={(e) => setCrtKeyword(e.target.value)}
                    placeholder="e.g. logistics"
                  />
                </label>
                <label className="flex flex-col gap-2 font-medium text-slate-300">
                  CRT Limit
                  <input
                    className="rounded-xl border border-white/10 bg-[#0f172a] text-white px-4 py-3 outline-none transition-colors focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                    type="number"
                    min={100}
                    max={20000}
                    step={100}
                    value={crtLimit}
                    onChange={(e) => setCrtLimit(Number(e.target.value) || 3000)}
                  />
                </label>
                <label className="flex flex-col gap-2 font-medium text-slate-300">
                  Min Quality
                  <input
                    className="rounded-xl border border-white/10 bg-[#0f172a] text-white px-4 py-3 outline-none transition-colors focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                    type="number"
                    min={0}
                    max={100}
                    value={minQualityThreshold}
                    onChange={(e) => setMinQualityThreshold(Number(e.target.value) || 50)}
                  />
                </label>
              </div>

              <label className="flex flex-col gap-2 font-medium text-slate-300">
                Search Queries <span className="text-xs font-normal text-slate-500">(One per line)</span>
                <textarea
                  className="min-h-40 resize-y rounded-xl border border-white/10 bg-[#0f172a] text-slate-300 px-4 py-3 font-mono text-sm leading-relaxed outline-none transition-colors focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                  value={queriesText}
                  onChange={(e) => setQueriesText(e.target.value)}
                />
              </label>

              <button
                className="mt-2 flex w-full items-center justify-center rounded-xl bg-indigo-600 px-6 py-4 text-sm font-bold text-white shadow-lg shadow-indigo-500/20 transition-all hover:bg-indigo-500 focus:ring-4 focus:ring-indigo-500/30 disabled:pointer-events-none disabled:bg-white/5 disabled:text-slate-500"
                onClick={runDiscovery}
                disabled={isDiscovering || isExtracting || (source !== "crt" && queries.length === 0)}
              >
                {isDiscovering ? (
                  <span className="flex items-center gap-2">
                    <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" className="opacity-25"></circle><path fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" className="opacity-75"></path></svg>
                    Running Discovery...
                  </span>
                ) : (
                  "Start Discovery"
                )}
              </button>
            </div>
          </section>

          {/* Extractor Panel */}
          <section className="rounded-3xl border border-white/5 bg-[#1e293b]/40 backdrop-blur-md p-6 shadow-xl">
            <h2 className="text-lg font-semibold text-white mb-5 flex items-center gap-3">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-500/20 text-sm text-emerald-400">2</span>
              Extraction Configuration
            </h2>

            <div className="flex flex-col gap-5 text-sm">
              <div className="grid grid-cols-2 gap-4">
                <label className="flex flex-col gap-2 font-medium text-slate-300">
                  Workers
                  <input
                    className="rounded-xl border border-white/10 bg-[#0f172a] text-white px-4 py-3 outline-none transition-colors focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                    type="number"
                    min={1}
                    max={20}
                    value={workers}
                    onChange={(e) => setWorkers(Number(e.target.value) || 5)}
                  />
                </label>

                <label className="flex flex-col gap-2 font-medium text-slate-300">
                  Max Pages / Site
                  <input
                    className="rounded-xl border border-white/10 bg-[#0f172a] text-white px-4 py-3 outline-none transition-colors focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                    type="number"
                    min={1}
                    max={10}
                    value={maxPages}
                    onChange={(e) => setMaxPages(Number(e.target.value) || 5)}
                  />
                </label>
                <label className="flex flex-col gap-2 font-medium text-slate-300">
                  Early Stop Score
                  <input
                    className="rounded-xl border border-white/10 bg-[#0f172a] text-white px-4 py-3 outline-none transition-colors focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                    type="number"
                    min={60}
                    max={100}
                    value={earlyStopScore}
                    onChange={(e) => setEarlyStopScore(Number(e.target.value) || 95)}
                  />
                </label>
                <label className="mb-1 flex items-center gap-2 text-xs font-medium text-slate-400">
                  <input
                    type="checkbox"
                    checked={mxValidation}
                    onChange={(e) => setMxValidation(e.target.checked)}
                    className="accent-emerald-500"
                  />
                  Validate MX (slower)
                </label>
                <label className="flex flex-col gap-2 font-medium text-slate-300">
                  Timeout (sec)
                  <input
                    className="rounded-xl border border-white/10 bg-[#0f172a] text-white px-4 py-3 outline-none transition-colors focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                    type="number"
                    min={5}
                    max={60}
                    value={extractTimeout}
                    onChange={(e) => setExtractTimeout(Number(e.target.value) || 15)}
                  />
                </label>
                <label className="flex flex-col gap-2 font-medium text-slate-300">
                  Min Delay (sec)
                  <input
                    className="rounded-xl border border-white/10 bg-[#0f172a] text-white px-4 py-3 outline-none transition-colors focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                    type="number"
                    min={0}
                    max={10}
                    step={0.1}
                    value={minDelay}
                    onChange={(e) => setMinDelay(Number(e.target.value) || 0.7)}
                  />
                </label>
                <label className="flex flex-col gap-2 font-medium text-slate-300">
                  Max Delay (sec)
                  <input
                    className="rounded-xl border border-white/10 bg-[#0f172a] text-white px-4 py-3 outline-none transition-colors focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                    type="number"
                    min={0}
                    max={20}
                    step={0.1}
                    value={maxDelay}
                    onChange={(e) => setMaxDelay(Number(e.target.value) || 1.8)}
                  />
                </label>
              </div>

              <button
                className="mt-2 flex w-full items-center justify-center rounded-xl bg-emerald-600 px-6 py-4 text-sm font-bold text-white shadow-lg shadow-emerald-500/20 transition-all hover:bg-emerald-500 focus:ring-4 focus:ring-emerald-500/30 disabled:pointer-events-none disabled:bg-white/5 disabled:text-slate-500"
                onClick={runExtractor}
                disabled={isDiscovering || isExtracting || isResetting || !targetsReady}
              >
                {isExtracting ? (
                  <span className="flex items-center gap-2">
                    <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" className="opacity-25"></circle><path fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" className="opacity-75"></path></svg>
                    Extracting Contacts...
                  </span>
                ) : (
                  "Start Extraction"
                )}
              </button>

              <button
                className="flex w-full items-center justify-center rounded-xl border border-rose-500/20 bg-rose-500/10 px-6 py-3 text-sm font-semibold text-rose-500 transition-all hover:bg-rose-500/20 hover:text-rose-400 disabled:pointer-events-none disabled:opacity-50"
                onClick={stopAndResetExtraction}
                disabled={isDiscovering || isResetting}
              >
                {isResetting ? "Stopping & Clearing..." : "Stop + Clear Extraction"}
              </button>
            </div>
          </section>

        </div>

        {/* Right Column: State & Logs */}
        <div className="flex w-full flex-col gap-8 lg:w-7/12 xl:w-2/3">
          <section className="rounded-2xl border border-white/5 bg-[#1e293b]/40 backdrop-blur-md p-6 shadow-sm">
            <div className="mb-4 flex flex-wrap items-end gap-3">
              <h2 className="mr-auto text-lg font-semibold text-white">Top Leads</h2>
              <label className="flex flex-col text-xs font-medium text-slate-400">
                Platform
                <select
                  className="mt-1 rounded-lg border border-white/10 bg-[#0f172a] text-slate-300 px-2 py-1 text-sm outline-none focus:border-indigo-500"
                  value={leadPlatform}
                  onChange={(e) => setLeadPlatform(e.target.value)}
                >
                  <option value="all">All</option>
                  <option value="shopify">Shopify</option>
                  <option value="woocommerce">WooCommerce</option>
                  <option value="magento">Magento</option>
                  <option value="bigcommerce">BigCommerce</option>
                  <option value="unknown">Unknown</option>
                </select>
              </label>
              <label className="flex flex-col text-xs font-medium text-slate-400">
                Status
                <select
                  className="mt-1 rounded-lg border border-white/10 bg-[#0f172a] text-slate-300 px-2 py-1 text-sm outline-none focus:border-indigo-500"
                  value={leadStatus}
                  onChange={(e) => setLeadStatus(e.target.value)}
                >
                  <option value="all">All</option>
                  <option value="ok">OK</option>
                  <option value="no_contact">No Contact</option>
                  <option value="error">Error</option>
                </select>
              </label>
              <label className="flex flex-col text-xs font-medium text-slate-400">
                Tier
                <select
                  className="mt-1 rounded-lg border border-white/10 bg-[#0f172a] text-slate-300 px-2 py-1 text-sm outline-none focus:border-indigo-500"
                  value={leadTier}
                  onChange={(e) => setLeadTier(e.target.value)}
                >
                  <option value="all">All</option>
                  <option value="tier_a">Tier A</option>
                  <option value="tier_b">Tier B</option>
                  <option value="tier_c">Tier C</option>
                </select>
              </label>
              <label className="flex flex-col text-xs font-medium text-slate-400">
                Min Score
                <input
                  className="mt-1 w-20 rounded-lg border border-white/10 bg-[#0f172a] text-slate-300 px-2 py-1 text-sm outline-none focus:border-indigo-500"
                  type="number"
                  min={0}
                  max={100}
                  value={leadMinScore}
                  onChange={(e) => setLeadMinScore(Number(e.target.value) || 0)}
                />
              </label>
              <label className="flex flex-col text-xs font-medium text-slate-400">
                Min Discovery
                <input
                  className="mt-1 w-24 rounded-lg border border-white/10 bg-[#0f172a] text-slate-300 px-2 py-1 text-sm outline-none focus:border-indigo-500"
                  type="number"
                  min={0}
                  max={100}
                  value={leadMinDiscoveryQuality}
                  onChange={(e) => setLeadMinDiscoveryQuality(Number(e.target.value) || 0)}
                />
              </label>
              <label className="flex flex-col text-xs font-medium text-slate-400">
                Contact Source
                <select
                  className="mt-1 rounded-lg border border-white/10 bg-[#0f172a] text-slate-300 px-2 py-1 text-sm outline-none focus:border-indigo-500"
                  value={leadContactSource}
                  onChange={(e) => setLeadContactSource(e.target.value)}
                >
                  <option value="all">All</option>
                  <option value="mailto">Mailto</option>
                  <option value="visible">Visible</option>
                  <option value="policy">Policy</option>
                  <option value="jsonld">JSON-LD</option>
                  <option value="obfuscated">Obfuscated</option>
                  <option value="social_profile">Social Profile</option>
                  <option value="domain_guess">Domain Guess</option>
                </select>
              </label>
              <label className="flex flex-col text-xs font-medium text-slate-400">
                Limit
                <input
                  className="mt-1 w-20 rounded-lg border border-white/10 bg-[#0f172a] text-slate-300 px-2 py-1 text-sm outline-none focus:border-indigo-500"
                  type="number"
                  min={5}
                  max={200}
                  value={leadLimit}
                  onChange={(e) => setLeadLimit(Number(e.target.value) || 25)}
                />
              </label>
              <label className="mb-1 flex items-center gap-2 text-xs font-medium text-slate-400">
                <input
                  className="rounded border-white/10 bg-[#0f172a]"
                  type="checkbox"
                  checked={hasEmailOnly}
                  onChange={(e) => setHasEmailOnly(e.target.checked)}
                />
                Email Only
              </label>
              <label className="mb-1 flex items-center gap-2 text-xs font-medium text-slate-400">
                <input
                  className="rounded border-white/10 bg-[#0f172a]"
                  type="checkbox"
                  checked={leadHealthyOnly}
                  onChange={(e) => setLeadHealthyOnly(e.target.checked)}
                />
                Healthy Only
              </label>
            </div>

            <div className="overflow-x-auto rounded-xl border border-white/10 bg-[#0f172a]">
              <table className="w-full text-left text-sm whitespace-nowrap">
                <thead>
                  <tr className="border-b border-white/10 bg-white/5 text-slate-400">
                    <th className="px-3 py-3 font-medium">Domain</th>
                    <th className="px-3 py-3 font-medium">Best Contact</th>
                    <th className="px-3 py-3 font-medium">Platform</th>
                    <th className="px-3 py-3 font-medium">Source</th>
                    <th className="px-3 py-3 font-medium">Discovery</th>
                    <th className="px-3 py-3 font-medium">Confidence</th>
                    <th className="px-3 py-3 font-medium">Score v2</th>
                    <th className="px-3 py-3 font-medium">Tier</th>
                    <th className="px-3 py-3 font-medium">Socials</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10">
                  {topLeads.map((lead) => (
                    <tr className="transition-colors hover:bg-white/5" key={`${lead.domain}-${lead.email_primary}-${lead.lead_score_v2}`}>
                      <td className="px-3 py-3 font-medium text-slate-200">{lead.domain || "-"}</td>
                      <td className="px-3 py-3 text-slate-300">
                        {lead.best_contact_value || lead.email_primary || "-"}
                        <div className="text-xs text-slate-500">{lead.best_contact_type || "-"}</div>
                      </td>
                      <td className="px-3 py-3 text-slate-300">{lead.platform}</td>
                      <td className="px-3 py-3 text-slate-300">{lead.email_source || "-"}</td>
                      <td className="px-3 py-3 text-slate-300">{lead.discovery_quality_score}</td>
                      <td className="px-3 py-3 text-slate-300">{lead.contact_confidence_score}</td>
                      <td className="px-3 py-3 text-slate-300">
                        <span className="inline-flex rounded-full bg-indigo-500/10 px-2 py-1 text-xs font-medium text-indigo-400 ring-1 ring-inset ring-indigo-500/20">
                          {lead.lead_score_v2}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-slate-300">
                        <span className="inline-flex rounded-full bg-emerald-500/10 px-2 py-1 text-xs font-medium text-emerald-400 ring-1 ring-inset ring-emerald-500/20">
                          {lead.tier}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-slate-300">{lead.socials_count}</td>
                    </tr>
                  ))}
                  {topLeads.length === 0 ? (
                    <tr>
                      <td className="px-3 py-6 text-center text-slate-400" colSpan={9}>
                        No leads match the current filters.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </section>

          <section className="rounded-2xl border border-white/5 bg-[#1e293b]/40 backdrop-blur-md p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-white mb-4">Extraction Progress</h2>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <div className="rounded-xl border border-white/5 bg-[#0f172a]/50 p-3">
                <div className="text-xs text-slate-400">Processed</div>
                <div className="text-xl font-bold text-slate-200">
                  {progress.processed.toLocaleString()}/{progress.total.toLocaleString()}
                </div>
              </div>
              <div className="rounded-xl border border-white/5 bg-[#0f172a]/50 p-3">
                <div className="text-xs text-slate-400">Remaining</div>
                <div className="text-xl font-bold text-slate-200">{progress.remaining.toLocaleString()}</div>
              </div>
              <div className="rounded-xl border border-white/5 bg-[#0f172a]/50 p-3">
                <div className="text-xs text-slate-400">Emails Found</div>
                <div className="text-xl font-bold text-slate-200">{progress.emails_found.toLocaleString()}</div>
              </div>
              <div className="rounded-xl border border-white/5 bg-[#0f172a]/50 p-3">
                <div className="text-xs text-slate-400">Run State</div>
                <div className={`text-sm font-semibold ${progress.running ? "text-indigo-400" : "text-slate-300"}`}>
                  {progress.running ? "Running" : "Idle"}
                </div>
              </div>
            </div>
            <div className="mt-3 text-xs text-slate-400">
              Last update:{" "}
              {progress.updated_at
                ? new Date(progress.updated_at).toLocaleString(undefined, {
                    dateStyle: "medium",
                    timeStyle: "short",
                  })
                : "-"}
            </div>
            <div className="mt-2 text-xs text-slate-400">
              Tiers: A {progress.pct_tier_a}% | B {progress.pct_tier_b}% | C {progress.pct_tier_c}% | Avg pages{" "}
              {progress.avg_pages_scanned} | Avg sec/domain {progress.avg_seconds_per_domain} | Throughput{" "}
              {progress.throughput_domains_per_minute}/min | Priority pages {progress.priority_pages_scanned} | Sitemap
              URLs {progress.sitemap_urls_examined} | Retries {progress.retries_used_total}
            </div>
          </section>
          
          {/* History / Status Table */}
          <section className="flex flex-col rounded-2xl border border-white/5 bg-[#1e293b]/40 backdrop-blur-md shadow-sm overflow-hidden">
            <div className="border-b border-white/5 bg-transparent px-6 py-4">
              <h2 className="text-lg font-semibold text-white">Active Datasets</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-white/5 bg-white/5 text-slate-400">
                    <th className="px-6 py-4 font-medium">Dataset Type</th>
                    <th className="px-6 py-4 font-medium">Last Run Time</th>
                    <th className="px-6 py-4 font-medium">Items Count</th>
                    <th className="px-6 py-4 font-medium">File Size</th>
                    <th className="px-6 py-4 font-medium">Data Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 bg-transparent">
                  {historyRows.map((row) => (
                    <tr key={row.key} className="transition-colors hover:bg-white/5">
                      <td className="px-6 py-4 font-medium text-slate-200">{row.label}</td>
                      <td className="px-6 py-4 text-slate-400">
                        {row.lastModified ? new Date(row.lastModified).toLocaleString(undefined, {
                          dateStyle: 'medium',
                          timeStyle: 'short'
                        }) : "-"}
                      </td>
                      <td className="px-6 py-4 text-slate-300">{row.count.toLocaleString()}</td>
                      <td className="px-6 py-4 text-slate-400">{row.sizeLabel}</td>
                      <td className="px-6 py-4">
                        <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${
                          row.ready ? "bg-emerald-500/10 text-emerald-400 ring-emerald-500/20" : "bg-white/5 text-slate-400 ring-white/10"
                        }`}>
                          {row.ready ? "✓ Ready" : "Pending"}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {historyRows.length === 0 ? (
                    <tr>
                      <td className="px-6 py-8 text-center text-slate-400" colSpan={5}>
                        No datasets have been generated yet.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </section>

          {/* Console / Terminal Output */}
          <section className="flex flex-1 flex-col rounded-2xl border border-[#0f172a] bg-[#020617] shadow-lg overflow-hidden min-h-100 relative">
            <div className="flex items-center justify-between border-b border-white/5 bg-[#0f172a] px-4 py-3">
              <div className="flex items-center gap-2 text-xs font-medium text-slate-400">
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                System Terminal
              </div>
              <div className="flex gap-1.5">
                <div className="h-3 w-3 rounded-full bg-[#1e293b]"></div>
                <div className="h-3 w-3 rounded-full bg-[#1e293b]"></div>
                <div className="h-3 w-3 rounded-full bg-[#1e293b]"></div>
              </div>
            </div>
            <div className="flex-1 overflow-auto p-4 z-10 selection:bg-indigo-500/30">
              <pre className="font-mono text-[13px] leading-tight text-indigo-300 whitespace-pre-wrap">{logText}</pre>
            </div>
            {/* Terminal Background Glow */}
            <div className="pointer-events-none absolute bottom-0 right-0 h-64 w-64 -translate-y-12 translate-x-12 rounded-full bg-indigo-500/10 blur-[80px]"></div>
          </section>

        </div>
        
      
      </main>
        <footer className="relative mt-16 flex flex-col items-center justify-center text-center pb-8 border-t border-white/5 pt-8 z-10">
          <p className="text-slate-400 text-sm mb-4">Need help understanding how to use the app for different niches?</p>
          <Link href="/docs" className="inline-flex items-center justify-center px-6 py-3 border border-white/10 shadow-lg text-sm font-medium rounded-xl text-white bg-[#1e293b]/60 backdrop-blur-md hover:bg-[#1e293b] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-[#0f172a] focus:ring-indigo-500 transition-all hover:shadow-indigo-500/20">
            <svg className="-ml-1 mr-2 h-4 w-4 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
            Read the User Guide &amp; Documentation
          </Link>
        </footer>
    </div>
  );
}
