// Cross-CDN, expanded: multiple endpoints PER provider to confirm the behavior is
// provider-level, not site-level. Low rate (1 req/method/host). We read the CDN's
// own fingerprint headers and flag when the CDN ITSELF stamps the rejection
// (server=CloudFront + "Error from cloudfront" = edge block, vs a plain origin 4xx).
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const HOSTS = [
  ['CloudFront', 'https://aws.amazon.com/'],
  ['CloudFront', 'https://d1.awsstatic.com/'],
  ['CloudFront', 'https://docs.aws.amazon.com/'],
  ['Cloudflare', 'https://www.cloudflare.com/cdn-cgi/trace'],
  ['Cloudflare', 'https://discord.com/'],
  ['Cloudflare', 'https://www.reddit.com/'],
  ['Fastly',     'https://www.fastly.com/'],
  ['Fastly',     'https://raw.githubusercontent.com/ArVaViT/http-query-lab/main/README.md'],
  ['Fastly',     'https://developer.mozilla.org/en-US/'],
  ['Netlify',    'https://www.netlify.com/'],
  ['Vercel',     'https://http-query-lab.vercel.app/api/echo'],
];
const METHODS = ['GET', 'QUERY', 'PROPFIND'];

function fp(h) {
  const pick = ['server', 'via', 'x-cache', 'cf-ray', 'x-amz-cf-id', 'x-served-by', 'x-vercel-id', 'x-vercel-mitigated', 'x-nf-request-id'];
  return pick.map((k) => (h.get(k) ? `${k}=${h.get(k).slice(0, 32)}` : null)).filter(Boolean).join(' | ');
}
function edgeVerdict(status, h) {
  const srv = (h.get('server') || '').toLowerCase();
  const xc = (h.get('x-cache') || '').toLowerCase();
  if (h.get('x-vercel-mitigated')) return 'EDGE-BLOCK (vercel challenge)';
  if (srv.includes('cloudfront') && (status === 403 || xc.includes('error'))) return 'EDGE-BLOCK (cloudfront)';
  if (srv === 'netlify' && (status === 405 || status === 403)) return 'edge/platform 4xx (netlify)';
  if (status >= 500) return 'origin/edge 5xx';
  if (status === 200 || status === 301 || status === 302) return 'FORWARDED (ok/redirect)';
  return `passed-through? origin ${status}`;
}

for (const [cdn, url] of HOSTS) {
  console.log(`\n=== [${cdn}] ${url} ===`);
  for (const m of METHODS) {
    try {
      const opt = m === 'GET' ? {} : { method: m, body: m === 'PROPFIND' ? undefined : '{"q":"x"}' };
      const r = await fetch(url, { ...opt, redirect: 'manual' });
      console.log(`  ${m.padEnd(9)} ${String(r.status).padEnd(4)} ${edgeVerdict(r.status, r.headers)}`);
      console.log(`            ${fp(r.headers)}`);
    } catch (e) { console.log(`  ${m.padEnd(9)} ERR  ${e.message}`); }
    await sleep(1500);
  }
}
