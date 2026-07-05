import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static export: `next build` emits plain HTML/JS/CSS into out/, which the
  // orchestrator embeds (go:embed) and serves natively — one binary, no Node in
  // production. The app is fully client-driven (polls the API), so nothing
  // needs a server.
  output: "export",

  // Pin the workspace root to this app — a stray lockfile in $HOME otherwise
  // makes Turbopack infer the wrong root.
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
