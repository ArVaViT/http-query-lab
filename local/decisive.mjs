// DECISIVE test for finding #1: is the Vercel challenge triggered by the
// METHOD (QUERY) or by fingerprint / body / burst volume?
// Phase A: same fingerprint (node/undici), sequential cold bursts, cleanest-first.
// Phase B: QUERY burst from three different fingerprints, each cold + spaced.
import { spawnSync } from 'node:child_process';

const URL = 'https://http-query-lab.vercel.app/api/echo';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function firstChallenge(codes) {
  const i = codes.findIndex((c) => c === 403);
  return i === -1 ? 'none (all clean)' : `req #${i + 1}`;
}

// undici burst
async function nodeBurst(method, n = 20, gap = 400) {
  const codes = [];
  for (let i = 0; i < n; i++) {
    try {
      const opt = method === 'GET' ? {} : { method, body: '{"q":"d"}', headers: { 'content-type': 'application/json' } };
      const r = await fetch(URL, opt);
      codes.push(r.status);
    } catch { codes.push('ERR'); }
    await sleep(gap);
  }
  return codes;
}

// curl / .NET bursts via child process, QUERY only
function curlQuery(n = 20, gap = 400) {
  const codes = [];
  for (let i = 0; i < n; i++) {
    const r = spawnSync('curl.exe', ['-s', '-o', 'NUL', '-w', '%{http_code}', '-X', 'QUERY', URL, '-d', '{"q":"d"}'], { encoding: 'utf8' });
    codes.push(parseInt(r.stdout.trim(), 10));
    spawnSync('cmd', ['/c', 'ping', '-n', '1', '-w', String(gap), '127.0.0.1'], { stdio: 'ignore' });
  }
  return codes;
}

console.log('=== PHASE A: method isolation, single node/undici fingerprint, sequential ===');
const getCodes = await nodeBurst('GET');
console.log('GET   x20:', getCodes.join(','), '=> first challenge:', firstChallenge(getCodes));
console.log('cooldown 90s...'); await sleep(90000);
const postCodes = await nodeBurst('POST');
console.log('POST  x20:', postCodes.join(','), '=> first challenge:', firstChallenge(postCodes));
console.log('cooldown 90s...'); await sleep(90000);
const queryCodes = await nodeBurst('QUERY');
console.log('QUERY x20:', queryCodes.join(','), '=> first challenge:', firstChallenge(queryCodes));

console.log('\n=== PHASE B: QUERY burst across fingerprints (each cold, spaced) ===');
console.log('node/undici QUERY already above:', firstChallenge(queryCodes));
console.log('cooldown 120s for fresh fingerprint...'); await sleep(120000);
const curlCodes = curlQuery();
console.log('curl  QUERY x20:', curlCodes.join(','), '=> first challenge:', firstChallenge(curlCodes));

console.log('\n=== VERDICT INPUTS ===');
console.log(JSON.stringify({
  get_first_challenge: firstChallenge(getCodes),
  post_first_challenge: firstChallenge(postCodes),
  query_node_first_challenge: firstChallenge(queryCodes),
  query_curl_first_challenge: firstChallenge(curlCodes),
}, null, 2));
