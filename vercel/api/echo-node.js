// Vercel Node function: echo the HTTP method and body (QUERY-aware).
module.exports = (req, res) => {
  let body = '';
  req.on('data', (c) => (body += c));
  req.on('end', () => {
    res.setHeader('content-type', 'application/json');
    res.setHeader('access-control-allow-origin', '*');
    res.status(200).json({
      runtime: 'node:' + process.version,
      method: req.method,
      body,
    });
  });
};
