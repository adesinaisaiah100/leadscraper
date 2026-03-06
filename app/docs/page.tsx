import Link from "next/link";

export default function DocsPage() {
  return (
    <div className="min-h-screen bg-[#0f172a] text-slate-300 font-sans selection:bg-indigo-500/30">
      {/* Top Navbar */}
      <nav className="sticky top-0 z-50 w-full border-b border-white/10 bg-[#0f172a]/80 backdrop-blur-md">
        <div className="flex h-16 w-full items-center px-6 lg:px-12">
          <Link 
            href="/" 
            className="group flex items-center gap-2 text-sm font-medium text-indigo-400 hover:text-indigo-300 transition-colors"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-500/10 group-hover:bg-indigo-500/20 transition-colors">
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
            </div>
            Back to Dashboard
          </Link>
        </div>
      </nav>

      <main className="w-full px-6 lg:px-12 py-12 lg:py-20 flex flex-col gap-24">
        {/* Header Section */}
        <header className="w-full max-w-7xl mx-auto">
          <h1 className="text-5xl lg:text-7xl font-extrabold tracking-tight text-white mb-6">
            Lead Scraper <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-cyan-400">User Guide</span>
          </h1>
          <p className="text-xl lg:text-2xl text-slate-400 max-w-3xl leading-relaxed">
            Your non-technical manual for finding and extracting high-quality business contacts for both E-commerce stores and General Niches.
          </p>
        </header>

        {/* How it Works - Full Width Grid */}
        <section className="w-full relative max-w-7xl mx-auto">
          <div className="absolute inset-0 bg-indigo-500/5 blur-[100px] rounded-full" />
          <div className="relative">
            <h2 className="text-3xl font-bold text-white mb-10 flex items-center gap-4">
              <div className="h-px bg-white/10 flex-1 max-w-[40px]"></div>
              How the Engine Works
              <div className="h-px bg-white/10 flex-1"></div>
            </h2>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-10">
              <div className="group relative bg-[#1e293b]/50 hover:bg-[#1e293b] p-8 lg:p-10 rounded-3xl border border-white/5 hover:border-indigo-500/30 transition-all duration-300">
                <div className="absolute -top-4 -left-4 w-12 h-12 bg-blue-500/20 text-blue-400 flex items-center justify-center rounded-2xl font-bold text-xl border border-blue-500/20 rotate-[-rotated]">1</div>
                <h3 className="text-xl font-bold text-white mb-4 mt-2 group-hover:text-blue-400 transition-colors">Discovery</h3>
                <p className="text-slate-400 leading-relaxed">
                  The app searches the internet (via DuckDuckGo or Certificate Transparency logs) to mass-discover websites matching your target keywords.
                </p>
              </div>

              <div className="group relative bg-[#1e293b]/50 hover:bg-[#1e293b] p-8 lg:p-10 rounded-3xl border border-white/5 hover:border-indigo-500/30 transition-all duration-300">
                <div className="absolute -top-4 -left-4 w-12 h-12 bg-indigo-500/20 text-indigo-400 flex items-center justify-center rounded-2xl font-bold text-xl border border-indigo-500/20">2</div>
                <h3 className="text-xl font-bold text-white mb-4 mt-2 group-hover:text-indigo-400 transition-colors">Scrape &amp; Score</h3>
                <p className="text-slate-400 leading-relaxed">
                  It visits each website&apos;s homepage, validating if the site is a real, healthy business, checks its platform, and assigns a preliminary &quot;Quality Score&quot;.
                </p>
              </div>

              <div className="group relative bg-[#1e293b]/50 hover:bg-[#1e293b] p-8 lg:p-10 rounded-3xl border border-white/5 hover:border-indigo-500/30 transition-all duration-300">
                <div className="absolute -top-4 -left-4 w-12 h-12 bg-emerald-500/20 text-emerald-400 flex items-center justify-center rounded-2xl font-bold text-xl border border-emerald-500/20">3</div>
                <h3 className="text-xl font-bold text-white mb-4 mt-2 group-hover:text-emerald-400 transition-colors">Extraction</h3>
                <p className="text-slate-400 leading-relaxed">
                  The app deeply scans only the high-quality sites to uncover hidden emails, specific contact pages, and social media profiles.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Full Settings & Configuration Guide */}
        <section className="w-full relative max-w-7xl mx-auto">
          <h2 className="text-3xl font-bold text-white mb-10 flex items-center gap-4">
            <div className="h-px bg-white/10 flex-1 max-w-[40px]"></div>
            App Configuration Guide
            <div className="h-px bg-white/10 flex-1"></div>
          </h2>

          <div className="space-y-6">
            {/* Discovery Config */}
            <div className="bg-[#1e293b]/40 rounded-3xl border border-white/5 overflow-hidden">
              <div className="p-6 bg-blue-500/10 border-b border-white/5">
                <h3 className="text-xl font-bold text-blue-400 flex items-center gap-2">
                  <span className="w-6 h-6 rounded bg-blue-500/20 flex items-center justify-center text-sm">1</span>
                  Discovery Settings
                </h3>
              </div>
              <div className="p-8 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                <div>
                  <h4 className="text-white font-semibold mb-2">Source Mode</h4>
                  <p className="text-sm text-slate-400 leading-relaxed">
                    <strong className="text-slate-300">DDG Only:</strong> Uses DuckDuckGo search. Best for local businesses &amp; general niches.<br/>
                    <strong className="text-slate-300">CRT Only:</strong> Scans SSL certificates. Best for E-Commerce/Shopify discovery.<br/>
                    <strong className="text-slate-300">Combined:</strong> Uses both for maximum coverage.
                  </p>
                </div>
                <div>
                  <h4 className="text-white font-semibold mb-2">Pages per Query</h4>
                  <p className="text-sm text-slate-400 leading-relaxed">How deep the search engine should look for each keyword. Usually, 2-5 pages is the sweet spot. Higher depth equals more leads, but lower relevance.</p>
                </div>
                <div>
                  <h4 className="text-white font-semibold mb-2">CRT Keyword &amp; Limit</h4>
                  <p className="text-sm text-slate-400 leading-relaxed">Only used in CRT or Combined mode. Represents the domain wildcard (e.g., &quot;logistics&quot;) and the max certificates to pull (up to 20,000).</p>
                </div>
                <div>
                  <h4 className="text-white font-semibold mb-2">Min Quality</h4>
                  <p className="text-sm text-slate-400 leading-relaxed">Filters out junk parked domains <em>before</em> extraction. Set to <strong>50+</strong> for E-commerce (they have carts). Set to <strong>10 or 20</strong> for local businesses (they don&apos;t have carts).</p>
                </div>
                <div className="md:col-span-2">
                  <h4 className="text-white font-semibold mb-2">Search Queries</h4>
                  <p className="text-sm text-slate-400 leading-relaxed">Enter one query per line. Use Google dorks like <code>inurl:myshopify.com &quot;shoes&quot;</code> to hyper-target your discovery phase.</p>
                </div>
              </div>
            </div>

            {/* Extraction Config */}
            <div className="bg-[#1e293b]/40 rounded-3xl border border-white/5 overflow-hidden">
              <div className="p-6 bg-emerald-500/10 border-b border-white/5">
                <h3 className="text-xl font-bold text-emerald-400 flex items-center gap-2">
                  <span className="w-6 h-6 rounded bg-emerald-500/20 flex items-center justify-center text-sm">2</span>
                  Extraction Settings
                </h3>
              </div>
              <div className="p-8 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                <div>
                  <h4 className="text-white font-semibold mb-2">Workers</h4>
                  <p className="text-sm text-slate-400 leading-relaxed">Controls concurrency. 5-10 workers is safe. Going over 15 may get your IP temporarily restricted by Cloudflare-protected sites.</p>
                </div>
                <div>
                  <h4 className="text-white font-semibold mb-2">Max Pages / Site</h4>
                  <p className="text-sm text-slate-400 leading-relaxed">How many sub-pages (like /about, /contact) the app should crawl per domain to find emails. 3-5 is usually enough.</p>
                </div>
                <div>
                  <h4 className="text-white font-semibold mb-2">Early Stop Score</h4>
                  <p className="text-sm text-slate-400 leading-relaxed">If the app finds an email yielding a score higher than this (e.g., 95), it immediately stops crawling that domain to save time.</p>
                </div>
                <div>
                  <h4 className="text-white font-semibold mb-2">Validate MX</h4>
                  <p className="text-sm text-slate-400 leading-relaxed">Checks if the discovered email actually has a valid mail server. Turn on for higher quality, turn off for faster scraping.</p>
                </div>
                <div>
                  <h4 className="text-white font-semibold mb-2">Timeout &amp; Delays</h4>
                  <p className="text-sm text-slate-400 leading-relaxed"><strong>Timeout (15s):</strong> Skips slow sites.<br/><strong>Min/Max Delay (0.7s - 1.8s):</strong> Adds human-like random pauses between requests to prevent bans.</p>
                </div>
              </div>
            </div>
            
            {/* Table Filters */}
            <div className="bg-[#1e293b]/40 rounded-3xl border border-white/5 overflow-hidden">
              <div className="p-6 bg-purple-500/10 border-b border-white/5">
                <h3 className="text-xl font-bold text-purple-400 flex items-center gap-2">
                  <span className="w-6 h-6 rounded bg-purple-500/20 flex items-center justify-center text-sm">3</span>
                  Results &amp; Filtering
                </h3>
              </div>
              <div className="p-8 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                <div>
                  <h4 className="text-white font-semibold mb-2">Platform Filter</h4>
                  <p className="text-sm text-slate-400 leading-relaxed">Isolate platforms you care about (e.g., only show Shopify or WooCommerce leads).</p>
                </div>
                <div>
                  <h4 className="text-white font-semibold mb-2">Lead Tier</h4>
                  <p className="text-sm text-slate-400 leading-relaxed">Filter by A (Direct Emails found), B (Social profiles only), or C (Catch-all/None).</p>
                </div>
                <div>
                  <h4 className="text-white font-semibold mb-2">Healthy Only &amp; Has Email</h4>
                  <p className="text-sm text-slate-400 leading-relaxed">Toggles to instantly hide parked domains, broken templates, or leads without an email address.</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Strategies Section - Side by Side */}
        <section className="w-full max-w-7xl mx-auto">
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-8 lg:gap-12">
            
            {/* Strategy 1 */}
            <div className="bg-gradient-to-b from-[#1e293b] to-[#0f172a] p-8 lg:p-12 rounded-3xl border border-white/10 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-64 h-64 bg-cyan-500/10 blur-[80px]" />
              
              <div className="flex items-center gap-4 mb-6">
                <div className="p-3 bg-cyan-500/20 text-cyan-400 rounded-xl">
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z" /></svg>
                </div>
                <h2 className="text-3xl font-bold text-white">E-Commerce Scraping</h2>
              </div>
              <p className="text-lg text-slate-400 mb-10">Optimized for finding stores selling physical or digital products (Shopify, WooCommerce, etc).</p>
              
              <div className="space-y-8">
                <div>
                  <h3 className="text-sm font-bold uppercase tracking-wider text-cyan-400 mb-4 pb-2 border-b border-white/10">1. Required Queries</h3>
                  <ul className="space-y-3">
                    <li className="flex gap-3 text-slate-300">
                      <span className="text-cyan-500 mt-1">▹</span> 
                      <span><code className="bg-black/50 text-cyan-300 px-2 py-1 rounded text-sm break-all">inurl:myshopify.com &quot;clothing&quot;</code> (Obvious Shopify)</span>
                    </li>
                    <li className="flex gap-3 text-slate-300">
                      <span className="text-cyan-500 mt-1">▹</span> 
                      <span><code className="bg-black/50 text-cyan-300 px-2 py-1 rounded text-sm break-all">&quot;powered by shopify&quot; &quot;skincare&quot; -inurl:myshopify.com</code> (Custom domain Shopify)</span>
                    </li>
                  </ul>
                </div>

                <div>
                  <h3 className="text-sm font-bold uppercase tracking-wider text-cyan-400 mb-4 pb-2 border-b border-white/10">2. Optimal Settings</h3>
                  <ul className="space-y-3 text-sm text-slate-400">
                    <li className="flex justify-between border-b border-white/5 pb-2">
                      <span className="font-medium text-slate-300">Source Mode</span>
                      <span className="text-white bg-white/10 px-2 py-0.5 rounded">Combined (DDG + CRT)</span>
                    </li>
                    <li className="flex justify-between border-b border-white/5 pb-2">
                      <span className="font-medium text-slate-300">CRT Keyword</span>
                      <span className="text-white bg-white/10 px-2 py-0.5 rounded">clothing, fashion, apparel</span>
                    </li>
                    <li className="flex justify-between border-b border-white/5 pb-2">
                      <span className="font-medium text-slate-300">Min Quality</span>
                      <span className="text-white bg-cyan-500/20 px-2 py-0.5 rounded">50</span>
                    </li>
                  </ul>
                  <p className="text-xs text-slate-500 mt-3 leading-relaxed">
                    <strong>Why 50?</strong> Real e-commerce stores easily score above 50 because the app detects shopping carts and checkout links. Keep it high to ignore spam.
                  </p>
                </div>
              </div>
            </div>

            {/* Strategy 2 */}
            <div className="bg-gradient-to-b from-[#1e293b] to-[#0f172a] p-8 lg:p-12 rounded-3xl border border-white/10 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-64 h-64 bg-fuchsia-500/10 blur-[80px]" />

              <div className="flex items-center gap-4 mb-6">
                <div className="p-3 bg-fuchsia-500/20 text-fuchsia-400 rounded-xl">
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
                </div>
                <h2 className="text-3xl font-bold text-white">General Niche Scraping</h2>
              </div>
              <p className="text-lg text-slate-400 mb-10">Optimized for finding service businesses, agencies, local shops, or SaaS companies.</p>
              
              <div className="space-y-8">
                <div>
                  <h3 className="text-sm font-bold uppercase tracking-wider text-fuchsia-400 mb-4 pb-2 border-b border-white/10">1. Required Queries</h3>
                  <ul className="space-y-3">
                    <li className="flex gap-3 text-slate-300">
                      <span className="text-fuchsia-500 mt-1">▹</span> 
                      <span><code className="bg-black/50 text-fuchsia-300 px-2 py-1 rounded text-sm break-all">&quot;plumbing services&quot; &quot;dallas texas&quot;</code></span>
                    </li>
                    <li className="flex gap-3 text-slate-300">
                      <span className="text-fuchsia-500 mt-1">▹</span> 
                      <span><code className="bg-black/50 text-fuchsia-300 px-2 py-1 rounded text-sm break-all">&quot;digital marketing agency&quot; &quot;london&quot; &quot;contact us&quot;</code></span>
                    </li>
                  </ul>
                </div>

                <div>
                  <h3 className="text-sm font-bold uppercase tracking-wider text-fuchsia-400 mb-4 pb-2 border-b border-white/10">2. Optimal Settings</h3>
                  <ul className="space-y-3 text-sm text-slate-400">
                    <li className="flex justify-between border-b border-white/5 pb-2">
                      <span className="font-medium text-slate-300">Source Mode</span>
                      <span className="text-white bg-white/10 px-2 py-0.5 rounded">DDG Only</span>
                    </li>
                    <li className="flex justify-between border-b border-white/5 pb-2">
                      <span className="font-medium text-slate-300">Pages per Query</span>
                      <span className="text-white bg-white/10 px-2 py-0.5 rounded">3-5 (for more depth)</span>
                    </li>
                    <li className="flex justify-between border-b border-white/5 pb-2">
                      <span className="font-medium text-slate-300">Min Quality</span>
                      <span className="text-white bg-fuchsia-500/20 px-2 py-0.5 rounded">10 or 20</span>
                    </li>
                  </ul>
                  <p className="text-xs text-slate-500 mt-3 leading-relaxed">
                    <strong className="text-fuchsia-300">CRUCIAL:</strong> Lower the threshold! Service businesses do NOT have &quot;add to cart&quot; buttons. A threshold of 50 will filter out perfect local businesses.
                  </p>
                </div>
              </div>
            </div>

          </div>
        </section>

        {/* Understanding the Data */}
        <section className="w-full max-w-7xl mx-auto">
          <h2 className="text-3xl font-bold text-white mb-8 flex items-center gap-4">
            Understanding the Results
            <div className="h-px bg-white/10 flex-1"></div>
          </h2>
          
          <div className="bg-[#1e293b]/30 rounded-3xl border border-white/10 overflow-hidden">
            <div className="p-8 lg:p-12 border-b border-white/5">
              <div className="flex flex-col md:flex-row gap-6 items-start">
                <div className="flex-shrink-0 bg-indigo-500/20 p-4 rounded-2xl text-indigo-400">
                  <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
                </div>
                <div>
                  <h3 className="text-2xl font-bold text-white mb-3">Lead Score v2</h3>
                  <p className="text-slate-400 leading-relaxed text-lg">
                    A smart grade out of 100 representing outreach viability. It dynamically mixes the health of the website with the exact quality of the email extracted. 
                    Targeting <strong className="text-indigo-300">scores above 80 </strong> usually means you hit an exact email match on a perfectly healthy domain.
                  </p>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-white/5">
              <div className="p-8 lg:p-12 transition-colors hover:bg-white/[0.02]">
                <div className="text-emerald-400 font-bold text-xl mb-4 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-500"></span> 
                  Tier A
                </div>
                <p className="text-slate-400">
                  We found a primary email address clearly listed on the site, inside a social bio, or confidently guessed it based on their domain. The best targets.
                </p>
              </div>

              <div className="p-8 lg:p-12 transition-colors hover:bg-white/[0.02]">
                <div className="text-amber-400 font-bold text-xl mb-4 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-amber-500"></span> 
                  Tier B
                </div>
                <p className="text-slate-400">
                  We couldn&apos;t find a direct email, but we DID find their active Social Media links (Instagram, LinkedIn, etc). Ready for DM outreach.
                </p>
              </div>

              <div className="p-8 lg:p-12 transition-colors hover:bg-white/[0.02]">
                <div className="text-rose-400 font-bold text-xl mb-4 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-rose-500"></span> 
                  Tier C
                </div>
                <p className="text-slate-400">
                  Site was scanned but couldn&apos;t reveal specific public contacts or socials. A generic contact form might exist.
                </p>
              </div>
            </div>
          </div>
        </section>
        
        <footer className="w-full py-12 text-center text-slate-500 border-t border-white/10 mt-8">
          <p className="text-lg">Ready to scale? Head back out and launch your first pipeline.</p>
        </footer>
      </main>
    </div>
  );
}
