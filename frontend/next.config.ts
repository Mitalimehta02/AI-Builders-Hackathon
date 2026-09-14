import type { NextConfig } from "next";

// The browser only talks to this Next.js app. Requests under /api are forwarded to the FastAPI
// backend, so the backend needs no CORS setup. BACKEND_URL can point elsewhere once deployed.
const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backendUrl}/:path*` }];
  },
};

export default nextConfig;
