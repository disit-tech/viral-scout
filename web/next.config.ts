import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The exported JSON in data/ is read at build time (Vercel) or per request (local dev). The public demo reads
  // data-demo/ (VIRAL_SCOUT_DATA_DIR=data-demo), the anonymized copy committed for the GitHub-connected demo project.
  outputFileTracingIncludes: { "/**": ["./data/**/*.json", "./data-demo/**/*.json", "./content/**/*.md"] },
  poweredByHeader: false,
};

export default nextConfig;
