import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The exported JSON in data/ is read at build time (Vercel) or per request (local dev).
  outputFileTracingIncludes: { "/**": ["./data/**/*.json", "./content/**/*.md"] },
  poweredByHeader: false,
};

export default nextConfig;
