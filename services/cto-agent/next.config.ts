import type { NextConfig } from "next";

const config: NextConfig = {
  experimental: {
    serverActions: { bodySizeLimit: "2mb" },
  },
  turbopack: {
    root: __dirname,
  },
};

export default config;
