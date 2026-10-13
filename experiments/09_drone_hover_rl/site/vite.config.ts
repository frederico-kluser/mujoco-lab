import { resolve } from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// Em `npm run dev` a API (`/api/*`: JSON, o SSE do HUD e os streams MJPEG) é encaminhada para o
// `sim_site.py` — mesma origem para o browser, logo sem CORS (o servidor não o anuncia). Por omissão o
// porto de sempre (8080); outro backend: `SIM_API=http://127.0.0.1:8793 npm run dev`.
const API = process.env.SIM_API ?? "http://127.0.0.1:8080"

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": resolve(import.meta.dirname, "./src"),
    },
  },
  server: {
    proxy: {
      "/api": { target: API, changeOrigin: true },
    },
  },
})
