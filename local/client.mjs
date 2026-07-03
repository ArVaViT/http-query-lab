// undici fetch client: can Node SEND a QUERY request?
const r = await fetch('http://127.0.0.1:8600/echo', {
  method: 'QUERY',
  body: '{"q":"undici"}',
  headers: { 'content-type': 'application/json' },
});
console.log('undici fetch:', r.status, await r.text());
