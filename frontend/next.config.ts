import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    // Rewrite barrel imports to direct module paths so we only ship the icons /
    // motion primitives actually used. `lucide-react` is optimized by Next out
    // of the box; framer-motion and @base-ui/react are not, and they're imported
    // across nearly every component — adding them trims the client bundle and
    // speeds dev compiles.
    optimizePackageImports: ["framer-motion", "@base-ui/react"],
  },
};

export default nextConfig;
