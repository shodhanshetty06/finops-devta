import path from "path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    globals: true,
    // Playwright E2E specs (e2e/*.spec.ts) match vitest's default *.spec.ts
    // glob too - they're run via `npm run test:e2e` (playwright), not here.
    exclude: ["**/node_modules/**", "e2e/**"],
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
});
