import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// base "./" keeps every URL relative, so the app also works behind a
// proxy path, for example a hosted IDE (https://<ide-host>/app/<port>/).
export default defineConfig({
  base: "./",
  plugins: [react()],
  server: { proxy: { "/api": "http://localhost:8000" } },
});
