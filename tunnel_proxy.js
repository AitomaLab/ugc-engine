const http = require('http');
const httpProxy = require('http-proxy');

const proxy = httpProxy.createProxyServer({});

const server = http.createServer((req, res) => {
    // CORS Headers for the browser
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, PATCH, DELETE');
    res.setHeader('Access-Control-Allow-Headers', 'X-Requested-With,content-type');

    if (req.url.startsWith('/api')) {
        // Route to Backend (8000)
        req.url = req.url.replace('/api', ''); // Remove /api prefix for internal backend
        console.log(`[Proxy] API Request: ${req.url} -> http://localhost:8000`);
        proxy.web(req, res, { target: 'http://localhost:8000' });
    } else {
        // Route to Frontend (3000)
        console.log(`[Proxy] UI Request: ${req.url} -> http://localhost:3000`);
        proxy.web(req, res, { target: 'http://localhost:3000' });
    }
});

server.on('error', (err) => {
    console.error('[Proxy] Error:', err.message);
});

console.log('[Proxy] Starting on port 5000...');
server.listen(5000);
