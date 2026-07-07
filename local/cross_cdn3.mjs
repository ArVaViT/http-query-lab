// Expand the taxonomy to more edges. Single low-rate probes (pass-through map),
// non-abusive. Special interest: Akamai CO-AUTHORED RFC 10008 QUERY — do they
// block it at their own edge? Also Google Cloud CDN, Azure Front Door, Fly, Bunny.
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const HOSTS = [
  ['Akamai?',   'https://www.ibm.com/'],
  ['Akamai?',   'https://www.cisco.com/'],
  ['Akamai?',   'https://www.apple.com/'],
  ['Google?',   'https://www.google.com/'],
  ['Google?',   'https://cloud.google.com/'],
  ['Azure?',    'https://azure.microsoft.com/en-us/'],
  ['Azure?',    'https://www.microsoft.com/en-us/'],
  ['Fly.io',    'https://fly.io/'],
  ['Bunny',     'https://bunny.net/'],
  ['jsDelivr',  'https://fastly.jsdelivr.net/npm/react/package.json'],
];
const METHODS = ['GET', 'QUERY', 'PROPFIND'];

function idHeaders(h) {
  const keys = ['server', 'via', 'x-cache', 'x-akamai-transformed', 'x-akamai-request-id',
    'x-azure-ref', 'x-msedge-ref', 'x-served-by', 'cf-ray', 'x-amz-cf-id', 'fly-request-id',
    'x-fastly-request-id', 'x-goog-', 'x-guploader'];
  const out = [];
  for (const [k, v] of h) { if (keys.some((kk) => k.toLowerCase().startsWith(kk))) out.push(`${k}=${String(v).slice(0, 30)}`); }
  return out.join(' | ') || '(no id headers)';
}

for (const [cdn, url] of HOSTS) {
  console.log(`\n=== [${cdn}] ${url} ===`);
  for (const m of METHODS) {
    try {
      const opt = m === 'GET' ? {} : { method: m, body: m === 'PROPFIND' ? undefined : '{"q":"x"}' };
      const r = await fetch(url, { ...opt, redirect: 'manual' });
      console.log(`  ${m.padEnd(9)} ${String(r.status).padEnd(4)} ${idHeaders(r.headers)}`);
    } catch (e) { console.log(`  ${m.padEnd(9)} ERR  ${e.message}`); }
    await sleep(1500);
  }
}
