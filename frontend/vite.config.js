import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 개발 서버에서는 API 요청을 백엔드(8700)로 넘긴다. 배포 시에는 백엔드가 dist를 직접 서빙한다.
export default defineConfig({
  plugins: [vue()],
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8700' } },
  build: { chunkSizeWarningLimit: 900 },
})
