const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  app.use(
    '/api',
    createProxyMiddleware({
      target: 'http://127.0.0.1:5000',
      changeOrigin: true,
      logLevel: 'debug',
      agent: false, // Disable agent to prevent IPv6 issues
      headers: {
        Connection: 'keep-alive',
      },
      onProxyReq: (proxyReq, req, res) => {
        console.log('[Proxy]', req.method, req.path, '-> http://127.0.0.1:5000' + req.path);
      },
      onError: (err, req, res) => {
        console.error('Proxy error:', err);
        res.writeHead(500, {
          'Content-Type': 'text/plain',
        });
        res.end('Proxy error: ' + err.message);
      },
    })
  );
};
