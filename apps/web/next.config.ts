import type { NextConfig } from "next";

// One image for every environment: the API URL and product name are read at runtime from
// /env.js, never baked into the build.
const config: NextConfig = {
  output: "standalone",
  // `next dev` would otherwise write an AGENTS.md of tool instructions into the repository.
  agentRules: false,
  // The route indicator sits over the bottom-left corner, where the user menu is.
  devIndicators: false,
  poweredByHeader: false,
  reactStrictMode: true,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default config;
