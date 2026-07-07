// GAP #3 (uncovered by the research): do server frameworks ROUTE a QUERY request
// AND READ its body? Many stacks body-gate on POST/PUT. Test Express + Fastify.
import express from 'express';
import Fastify from 'fastify';

const BODY = '{"filter":"x","n":42}';
const out = {};

// ---- Express ----
const ex = express();
ex.use(express.text({ type: '*/*' }));
ex.all('/q', (req, res) => res.json({ method: req.method, bodyLen: (req.body || '').length, body: req.body }));
const exSrv = await new Promise((ok) => { const s = ex.listen(8690, '127.0.0.1', () => ok(s)); });

// ---- Fastify (needs addHttpMethod for QUERY) ----
const fa = Fastify();
try { fa.addHttpMethod('QUERY', { hasBody: true }); } catch (e) { out.fastify_addmethod = 'FAILED: ' + e.message; }
fa.addContentTypeParser('*', { parseAs: 'string' }, (req, body, done) => done(null, body));
try {
  fa.route({ method: 'QUERY', url: '/q', handler: async (req) => ({ method: req.method, bodyLen: (req.body || '').length, body: req.body }) });
} catch (e) { out.fastify_route = 'FAILED: ' + e.message; }
await fa.listen({ port: 8691, host: '127.0.0.1' });

async function hit(port) {
  try {
    const r = await fetch(`http://127.0.0.1:${port}/q`, { method: 'QUERY', body: BODY, headers: { 'content-type': 'application/json' } });
    return { status: r.status, ...(await r.json().catch(() => ({}))) };
  } catch (e) { return { error: e.message }; }
}

out.express = await hit(8690);
out.fastify = await hit(8691);

for (const [k, v] of Object.entries(out)) console.log(k, '->', JSON.stringify(v));
console.log('\nBODY_READ:',
  'express', out.express?.bodyLen === BODY.length ? 'YES' : `NO (${out.express?.bodyLen})`,
  '| fastify', out.fastify?.bodyLen === BODY.length ? 'YES' : `NO (${out.fastify?.bodyLen})`);
exSrv.close(); await fa.close(); process.exit(0);
