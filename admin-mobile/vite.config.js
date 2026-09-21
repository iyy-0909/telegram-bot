import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"

export default defineConfig(({ command }) => ({
  base: "/mobile/",
  plugins: [vue()],
  esbuild: command === "build"
    ? { drop: ["console", "debugger"] }
    : undefined,
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
}))
