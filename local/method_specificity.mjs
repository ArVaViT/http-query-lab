// Follow-up experiment: does Vercel's bot filter challenge QUERY SPECIFICALLY,
// or any uncommon/non-GET-POST method? Same client, sequential cold bursts.
// GET/PUT = controls (standard). PROPFIND = real but rare (WebDAV). QUERY = subject.
const URL = 'https://http-query-lab.vercel.app/api/echo';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function firstChallenge(codes) {
  const i = codes.findIndex((c) => c === 403);
  return i === -1 ? 'none (clean)' : `#${i + 1}`;
}

async function burst(method, n = 14, gap = 400) {
  const codes = [];
  for (let i = 0; i < n; i++) {
    try {
      const opt = method === 'GET'
        ? {}
        : { method, body: '{"q":"x"}', headers: { 'content-type': 'application/json' } };
      const r = await fetch(URL, opt);
      codes.push(r.status);
    } catch (e) { codes.push('ERR'); }
    await sleep(gap);
  }
  return codes;
}

const methods = ['GET', 'PUT', 'PROPFIND', 'QUERY'];
const result = {};
for (const m of methods) {
  const codes = await burst(m);
  result[m] = firstChallenge(codes);
  console.log(`${m.padEnd(9)} x14: ${codes.join(',')}  => challenge ${result[m]}`);
  console.log('cooldown 90s...');
  await sleep(90000);
}
console.log('\n=== VERDICT ===');
console.log(JSON.stringify(result, null, 2));
