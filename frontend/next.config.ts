import type { NextConfig } from "next";

// MIZAN_STATIC_EXPORT=1 builds a static site (`out/`) for static hosting (see render.yaml).
// Every route is prerendered; the browser calls the API at NEXT_PUBLIC_API_BASE_URL.
const staticExport = process.env.MIZAN_STATIC_EXPORT === "1";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  ...(staticExport ? { output: "export" as const, trailingSlash: true } : {}),
};

export default nextConfig;
