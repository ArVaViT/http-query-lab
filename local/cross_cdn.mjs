// Cross-CDN edge behavior toward QUERY / PROPFIND vs GET.
// LOW RATE (1 request per method per host, sequential, polite) — we are only
// observing whether each CDN's EDGE forwards a novel method to origin or rejects
// it at the edge. Burst/bot-challenge behavior needs our OWN origin behind each
// CDN (noted as a limitation); this maps pass-through, non-abusively.
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const HOSTS = [
  ['Cloudflare',  'https://www.cloudflare.com/cdn-cgi/trace'],
  ['Fastly',      'https://www.fastly.com/'],
  ['CloudFront',  'https://aws.amazon.com/'],
  ['jsDelivr',    'https://cdn.jsdelivr.net/npm/react/package.json'],
  ['Netlify',     'https://www.netlify.com/'],
  ['Postman-echo','https://postman-echo.com/get'],
  ['GitHub-raw',  'https://raw.githubusercontent.com/ArVaViT/http-query-lab/main/README.md'],
];
const METHODS = ['GET', 'QUERY', 'PROPFIND'];
const CDN_HEADERS = ['server', 'via', 'cf-ray', 'x-served-by', 'x-amz-cf-id', 'x-vercel-id', 'x-nf-request-id', 'x-cache', 'x-vercel-mitigated'];

function cdnFingerprint(h) {
  const out = [];
  for (const k of CDN_HEADERS) { const v = h.get(k); if (v) out.push(`${k}=${v.slice(0, 40)}`); }
  return out.join(' | ') || '(no cdn headers)';
}

for (const [name, url] of HOSTS) {
  console.log(`\n=== ${name}  ${url} ===`);
  for (const m of METHODS) {
    try {
      const opt = m === 'GET' ? {} : { method: m, body: m === 'PROPFIND' ? '' : '{"q":"x"}' };
      const r = await fetch(url, { ...opt, redirect: 'manual' });
      console.log(`  ${m.padEnd(9)} -> ${r.status} ${r.statusText}`);
      console.log(`             ${cdnFingerprint(r.headers)}`);
    } catch (e) {
      console.log(`  ${m.padEnd(9)} -> FETCH ERROR: ${e.message}`);
    }
    await sleep(1200); // polite
  }
}
