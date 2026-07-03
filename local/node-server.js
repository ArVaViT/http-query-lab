// Plain Node http server — does llhttp even parse a QUERY request line?
const http = require('http');

const server = http.createServer((req, res) => {
  let body = '';
  req.on('data', (c) => (body += c));
  req.on('end', () => {
    res.setHeader('content-type', 'application/json');
    res.end(JSON.stringify({ method: req.method, body }));
  });
});

server.on('clientError', (err, socket) => {
  console.error('CLIENT_ERROR:', err.code, err.message);
  socket.end('HTTP/1.1 400 Bad Request\r\n\r\n');
});

server.listen(8601, '127.0.0.1', () => console.log('node lab on :8601, version', process.version));
