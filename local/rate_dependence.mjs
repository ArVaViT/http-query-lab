// Does Vercel's QUERY challenge depend on RATE, or trip at any speed?
// This decides the real-world conclusion: "QUERY is broken on Vercel" vs
// "only bursts get challenged, normal low-rate traffic passes."
// Self-gated: wait for a provably-clean IP before each rate window.
// Also tests body-dependence (QUERY with vs without body) in a clean window.
const URL = 'https://http-query-lab.vercel.app/api/echo';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const stamp = () => new Date().toISOString().slice(11, 19);

async function get() { try { return (await fetch(URL)).status; } catch { return 'ERR'; } }

async function waitUntilClean(maxMin = 18) {
  let waited = 0;
  while (waited < maxMin * 60) {
    const a = await get(); await sleep(1500); const b = await get();
    if (a === 200 && b === 200) return true;
    console.log(`  [${stamp()}] flagged (GET=${a},${b}), wait 45s`);
    await sleep(45000); waited += 47;
  }
  return false;
}

async function queryBurst(n, gapMs, withBody = true) {
  const codes = [];
  for (let i = 0; i < n; i++) {
    try {
      const opt = withBody
        ? { method: 'QUERY', body: '{"q":"x"}', headers: { 'content-type': 'application/json' } }
        : { method: 'QUERY' };
      codes.push((await fetch(URL, opt)).status);
    } catch { codes.push('ERR'); }
    if (i < n - 1) await sleep(gapMs);
  }
  const fc = codes.findIndex((c) => c === 403);
  return { codes, firstChallenge: fc === -1 ? null : fc + 1 };
}

const results = {};
// Order: slowest first (most likely clean -> less contamination), then faster.
const RATES = [
  ['30s', 8, 30000],
  ['10s', 10, 10000],
  ['3s', 12, 3000],
  ['0.4s (baseline)', 14, 400],
];

for (const [label, n, gap] of RATES) {
  console.log(`\n[${stamp()}] === QUERY @ ${label} interval, ${n} reqs ===`);
  if (!(await waitUntilClean())) { results[label] = 'INCONCLUSIVE (no clean IP)'; continue; }
  const r = await queryBurst(n, gap);
  results[label] = r.firstChallenge ? `challenge #${r.firstChallenge}` : 'CLEAN (no challenge)';
  console.log(`[${stamp()}] ${label}: ${results[label]}  [${r.codes.join(',')}]`);
}

// Body-dependence: QUERY WITHOUT a body, fast rate, clean window.
console.log(`\n[${stamp()}] === QUERY no-body @ 0.4s ===`);
if (await waitUntilClean()) {
  const r = await queryBurst(14, 400, false);
  results['no-body @ 0.4s'] = r.firstChallenge ? `challenge #${r.firstChallenge}` : 'CLEAN';
  console.log(`[${stamp()}] no-body: ${results['no-body @ 0.4s']}  [${r.codes.join(',')}]`);
}

console.log(`\n[${stamp()}] === VERDICT ===`);
console.log(JSON.stringify(results, null, 2));
