// A/B: does a burst of QUERY requests trip Vercel's bot mitigation when an
// identical burst of GETs does not? Client = undici (currently unflagged).
const U = 'https://http-query-lab.vercel.app/api/echo';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function burst(method, n) {
  const codes = [];
  for (let i = 0; i < n; i++) {
    try {
      const r = await fetch(U, method === 'GET' ? {} : { method, body: '{"q":"ab"}', headers: { 'content-type': 'application/json' } });
      codes.push(r.status);
    } catch (e) {
      codes.push('ERR');
    }
    await sleep(400);
  }
  return codes;
}

console.log('phase1 GET burst x12:', (await burst('GET', 12)).join(','));
await sleep(30000);
console.log('phase1 GET recheck:', (await burst('GET', 2)).join(','));

console.log('phase2 QUERY burst x12:', (await burst('QUERY', 12)).join(','));
for (let i = 0; i < 8; i++) {
  await sleep(20000);
  const g = await burst('GET', 1);
  const q = await burst('QUERY', 1);
  console.log(`post-burst t+${(i + 1) * 20}s GET=${g[0]} QUERY=${q[0]}`);
  if (g[0] === 403 || q[0] === 403) break;
}
console.log('ab test done');
