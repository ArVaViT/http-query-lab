// RIGOROUS method-boundary map for Vercel's bot filter.
// Key fix vs the last run: the challenge flag persists >10min and hits ALL methods,
// so we SELF-GATE — before each candidate burst, poll GET until the IP is provably
// clean (2 consecutive 200s), removing cross-method contamination.
// Controls: (a) standard methods should never challenge; (b) Supabase edge (no bot
// filter) should pass every method; (c) trigger index only trusted from a clean start.

const VERCEL = 'https://http-query-lab.vercel.app/api/echo';
const SUPA = 'https://rrisqutxlkamwfhcashl.supabase.co/functions/v1/query-echo';
const SUPA_KEY = 'sb_publishable_G73OsUvWmpPZGOZCkn997g_0mEYLVtt';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const stamp = () => new Date().toISOString().slice(11, 19);

async function send(url, method, extraHeaders = {}) {
  const noBody = method === 'GET' || method === 'HEAD' || method === 'OPTIONS';
  const opt = noBody
    ? { method, headers: extraHeaders }
    : { method, body: '{"q":"x"}', headers: { 'content-type': 'application/json', ...extraHeaders } };
  try {
    const r = await fetch(url, opt);
    return r.status;
  } catch { return 'ERR'; }
}

async function burst(url, method, n = 14, gap = 400, headers = {}) {
  const codes = [];
  for (let i = 0; i < n; i++) { codes.push(await send(url, method, headers)); await sleep(gap); }
  return codes;
}
function firstChallenge(codes) { const i = codes.findIndex((c) => c === 403); return i === -1 ? null : i + 1; }

// Wait until the Vercel IP is provably clean: 2 consecutive GET 200s.
async function waitUntilClean(maxMin = 16) {
  const deadline = Date.now ? null : null; // Date.now unavailable in workflow; here plain node, ok
  let waited = 0;
  while (waited < maxMin * 60) {
    const a = await send(VERCEL, 'GET');
    await sleep(1500);
    const b = await send(VERCEL, 'GET');
    if (a === 200 && b === 200) return true;
    console.log(`  [${stamp()}] still flagged (GET=${a},${b}), waiting 45s...`);
    await sleep(45000); waited += 47;
  }
  return false;
}

const results = { vercel: {}, supabase: {} };

// ---- Phase 1: Vercel standard methods (should stay clean; chain them) ----
console.log(`[${stamp()}] PHASE 1 — Vercel standard methods`);
await waitUntilClean();
for (const m of ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']) {
  const codes = await burst(VERCEL, m, 12);
  const fc = firstChallenge(codes);
  results.vercel[m] = fc ? `challenge #${fc}` : 'clean';
  console.log(`  ${m.padEnd(9)} -> ${results.vercel[m]}  [${codes.slice(0, 6).join(',')}...]`);
  if (fc) { console.log('  (standard method flagged unexpectedly, clearing before next)'); await waitUntilClean(); }
}

// ---- Phase 2: Vercel uncommon methods, self-gated (each from a clean IP) ----
console.log(`\n[${stamp()}] PHASE 2 — Vercel uncommon methods (self-gated)`);
for (const m of ['QUERY', 'PROPFIND', 'SEARCH', 'REPORT', 'PURGE', 'MKCOL']) {
  console.log(`  [${stamp()}] clearing flag before ${m}...`);
  const clean = await waitUntilClean();
  if (!clean) { results.vercel[m] = 'INCONCLUSIVE (never got clean IP)'; console.log(`  ${m}: could not get clean IP`); continue; }
  const codes = await burst(VERCEL, m, 14);
  const fc = firstChallenge(codes);
  results.vercel[m] = fc ? `challenge #${fc}` : 'clean';
  console.log(`  [${stamp()}] ${m.padEnd(9)} -> ${results.vercel[m]}  [${codes.join(',')}]`);
}

// ---- Phase 3: Supabase control (no bot filter — expect all pass) ----
console.log(`\n[${stamp()}] PHASE 3 — Supabase edge control`);
const h = { Authorization: `Bearer ${SUPA_KEY}`, apikey: SUPA_KEY };
for (const m of ['GET', 'QUERY', 'PROPFIND', 'SEARCH', 'REPORT', 'PURGE']) {
  const codes = await burst(SUPA, m, 10, 300, h);
  const fc = firstChallenge(codes);
  results.supabase[m] = fc ? `challenge #${fc}` : `clean (${codes[0]})`;
  console.log(`  ${m.padEnd(9)} -> ${results.supabase[m]}`);
}

console.log(`\n[${stamp()}] === VERDICT ===`);
console.log(JSON.stringify(results, null, 2));
