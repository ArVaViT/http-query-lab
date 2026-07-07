// TEST for H1/H3: do edges distinguish OLD registered verbs from the NEW QUERY,
// or reject by a hard allowlist? Compare across method "age":
//   PROPFIND (WebDAV, RFC 2518, 1999) | SEARCH (RFC 5323, 2008) |
//   QUERY (RFC 10008, 2026)           | FOOBAR (never registered)
// Prediction:
//   - hard allowlist (CloudFront): ALL four rejected the same way
//   - stale method-table: old verbs handled, QUERY+FOOBAR rejected as unknown
//   - forwarder (Cloudflare/Fastly): all forwarded, origin varies
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const HOSTS = [
  ['CloudFront', 'https://docs.aws.amazon.com/'],
  ['Akamai',     'https://www.cisco.com/'],
  ['Akamai',     'https://www.apple.com/'],
  ['Google',     'https://cloud.google.com/'],
  ['Netlify',    'https://www.netlify.com/'],
  ['Bunny',      'https://bunny.net/'],
  ['Cloudflare', 'https://discord.com/'],
  ['Fastly',     'https://www.fastly.com/'],
];
const METHODS = ['GET', 'PROPFIND', 'SEARCH', 'QUERY', 'FOOBAR'];

for (const [cdn, url] of HOSTS) {
  const row = [];
  for (const m of METHODS) {
    try {
      const opt = m === 'GET' ? {} : { method: m };
      const r = await fetch(url, { ...opt, redirect: 'manual' });
      const srv = (r.headers.get('server') || '').slice(0, 14);
      row.push(`${m}=${r.status}${srv ? `(${srv})` : ''}`);
    } catch (e) { row.push(`${m}=ERR`); }
    await sleep(1300);
  }
  console.log(`[${cdn.padEnd(11)}] ${url}`);
  console.log(`   ${row.join('  ')}`);
}
