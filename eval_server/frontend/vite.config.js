import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],
    server: {
        port: 3001,
        host: true,
        proxy: {
            '/api': {
                target: 'http://127.0.0.1:5051',
                changeOrigin: true,
                rewrite: function (path) { return path.replace(/^\/api/, ''); },
            },
            '/brain': {
                target: 'http://127.0.0.1:5000',
                changeOrigin: true,
                rewrite: function (path) { return path.replace(/^\/brain/, ''); },
            }
        }
    }
});
