import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',   // Binds to all IPv4 interfaces
    port: 5173,
    strictPort: true,  // Prevents Vite from silently jumping to 5174 if busy
    allowedHosts: true // Allows incoming .loca.lt domains
  }
});