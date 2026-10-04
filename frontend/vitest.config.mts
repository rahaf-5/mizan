import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    include: ["tests/**/*.test.{ts,tsx}"],
    exclude: ["node_modules/**"],
    environment: "node", // component tests opt into jsdom per file
    setupFiles: ["./tests/setup.ts"],
  },
});
