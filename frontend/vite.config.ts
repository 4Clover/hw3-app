import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import {defineConfig, type ProxyOptions} from 'vite';
import type * as http from "http";

const configureProxy = (proxy : any, options: ProxyOptions) => {
  proxy.on('proxyReq', (proxyReq : http.ClientRequest, req: http.IncomingMessage, res: http.ServerResponse) => {
    console.log('Proxying request:', req.url)
  });
  proxy.on('error', (err: Error, req: http.IncomingMessage, res: http.ServerResponse) => {
    console.error('Proxy Error:', err);
    // sending a response in the event of a hanging request
    if (res && !res.headersSent) { // check if a response has been sent yet
      res.writeHead(500, {'Content-Type': 'text/plain'});
      res.end('Proxy error: ' + err.message);
    } else if (res && !res.writableEnded) { // end the response if it's still open
      res.end();
    }
  });
}


export default defineConfig(({ mode }) => ({
  plugins: [sveltekit(), tailwindcss()],
  server: mode === 'development' ? {
    proxy: {
      // changed to single as a catch-all for /api/* calls
      '/api': {
        target: 'http://backend:8000', // backend is service in Docker
        changeOrigin: true,
        secure: false, // Usually false for http targets
        configure: configureProxy
      },
      '/test/test-mongo': { // change for testing possibly
        target: 'http://backend:8000',
        changeOrigin: true,
        secure: false,
        configure: configureProxy
      }
    }
  } : undefined,
}));