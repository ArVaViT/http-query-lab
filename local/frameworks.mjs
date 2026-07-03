// Do Express and Fastify route a QUERY request that llhttp already parsed?
import express from 'express';
import Fastify from 'fastify';

const ex = express();
ex.use(express.text({ type: '*/*' }));
// is there a generated app.query() verb helper?
console.log('express has app.query verb:', typeof ex.query);
ex.all('/echo', (req, res) => res.json({ via: 'express.all', method: req.method, body: req.body }));
await new Promise((ok) => ex.listen(8610, '127.0.0.1', ok));

const fa = Fastify();
fa.route({ method: 'GET', url: '/echo', handler: async () => ({ via: 'fastify-get' }) });
let fastifyQueryRouteError = null;
try {
  fa.route({
    method: 'QUERY',
    url: '/echo',
    handler: async (req) => ({ via: 'fastify.route', method: req.method }),
  });
} catch (e) {
  fastifyQueryRouteError = e.message;
}
console.log('fastify QUERY route registration error:', fastifyQueryRouteError);
await fa.listen({ port: 8611, host: '127.0.0.1' });

for (const [name, port] of [['express', 8610], ['fastify', 8611]]) {
  try {
    const r = await fetch(`http://127.0.0.1:${port}/echo`, { method: 'QUERY', body: '{"q":"x"}', headers: { 'content-type': 'text/plain' } });
    console.log(`${name} QUERY ->`, r.status, (await r.text()).slice(0, 120));
  } catch (e) {
    console.log(`${name} QUERY -> FAIL`, e.message);
  }
}
process.exit(0);
