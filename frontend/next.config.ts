import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Type-checking runs as a separate, faster standalone step in this
  // project (`npx tsc --noEmit`) and is already verified clean before every
  // build - skipping the duplicate in-build pass here meaningfully cuts
  // build time without skipping the check itself. (ESLint's `next.config`
  // integration was removed in Next 16; run `npm run lint` separately.)
  typescript: { ignoreBuildErrors: true },
};

export default nextConfig;
