import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"

export default defineConfig({
  plugins: [vue()],
  base: "/",  // Root-relative paths for bundled deployment
  server: {
    port: 5173,
  },
  build: {
    outDir: "dist",
    assetsDir: "assets",
  },
})
