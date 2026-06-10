import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // For AWS App Runner / ECS containerised deploy:
  output: 'standalone',
};

export default nextConfig;
