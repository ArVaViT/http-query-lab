// Empirical method-normalization: send input method 'query' AND 'QUERY' from each
// JS client to a raw echo that reports the EXACT wire method. Settles the axios dispute.
import http from 'node:http';
import axios from 'axios';
import got from 'got';

const URL = 'http://127.0.0.1:8695/';
const body = '{"q":1}';

async function viaFetch(m) {
  try { const r = await fetch(URL, { method: m, body, headers: { 'content-type': 'application/json' } }); return (await r.text()).trim(); }
  catch (e) { return 'ERR:' + e.message.slice(0, 40); }
}
async function viaAxios(m) {
  try { const r = await axios({ url: URL, method: m, data: body, transformResponse: (x) => x }); return String(r.data).trim(); }
  catch (e) { return 'ERR:' + (e.response ? String(e.response.data).trim() : e.message.slice(0, 40)); }
}
async function viaGot(m) {
  try { const r = await got(URL, { method: m, body, throwHttpErrors: false }); return r.body.trim(); }
  catch (e) { return 'ERR:' + e.message.slice(0, 40); }
}
function viaRawHttp(m) {
  return new Promise((res) => {
    const req = http.request(URL, { method: m }, (r) => { let d = ''; r.on('data', (c) => (d += c)); r.on('end', () => res(d.trim())); });
    req.on('error', (e) => res('ERR:' + e.message.slice(0, 40)));
    req.end(body);
  });
}

const out = {};
for (const [name, fn] of [['fetch/undici', viaFetch], ['axios', viaAxios], ['got', viaGot], ['node http.request', viaRawHttp]]) {
  out[name] = { 'query': await fn('query'), 'QUERY': await fn('QUERY') };
}
console.log(JSON.stringify(out));
