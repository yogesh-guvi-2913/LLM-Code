# Deploy — TLS, domain, and the production edge

This directory holds the **deploy-time** edge config. Auth, metrics,
usage accounting, and the host-token preview scheme are all built and **proven on
localhost** (`scripts/auth-check.sh`, `/metrics`, `/v1/usage`). TLS + a real
wildcard domain is the one piece that genuinely **cannot** be proven without
`sandboxes.example.com` and live DNS — so it is documented here, not faked.

## What's already true (no edge needed)

- The preview already rides a single port with per-session host-token auth. Behind
  TLS this is unchanged — the token is the left-most host label, so HTTPS "just
  works" and the cross-origin-iframe cookie problem stays solved.
- The orchestrator mints preview URLs from `PREVIEW_DOMAIN` / `PREVIEW_PORT`. Point
  those at the public name and port and the URLs are production-correct.

## Option A — Caddy (fewest moving parts, single node)

`Caddyfile` terminates TLS for `sandboxes.example.com` and the
`*.preview.sandboxes.example.com` wildcard, auto-provisioning certs from Let's Encrypt
(DNS-01). Run the orchestrator bound to loopback (`LISTEN_ADDR=127.0.0.1:8090`) with
`PREVIEW_DOMAIN=preview.sandboxes.example.com PREVIEW_PORT=443`. WebSocket upgrades
(terminal + Vite HMR) pass through automatically.

```bash
# needs a Caddy build with your DNS provider module, e.g. cloudflare:
#   xcaddy build --with github.com/caddy-dns/cloudflare
CLOUDFLARE_API_TOKEN=… caddy run --config deploy/Caddyfile
```

## Option B — AWS ALB + ACM (fits the v2 ASG fleet)

When the orchestrator runs behind an Application Load Balancer:

1. **ACM cert** covering `sandboxes.example.com` **and** `*.preview.sandboxes.example.com`
   (one cert, two SANs). DNS-validate it.
2. **HTTPS:443 listener** with that cert. Two host-header rules, both forwarding to
   the orchestrator target group (the app splits the vhost itself):
   - `sandboxes.example.com` → control plane
   - `*.preview.sandboxes.example.com` → preview proxy
3. Enable **WebSocket** (ALB supports it natively; no extra config) and raise the
   idle timeout (e.g. 300s) so long-lived terminal/HMR sockets aren't cut.
4. Route 53: A/ALIAS records for the apex and the `*.preview` wildcard → the ALB.

Run the orchestrator with `PREVIEW_DOMAIN=preview.sandboxes.example.com PREVIEW_PORT=443`
(same as Caddy). The ALB is the TLS terminator; the app stays HTTP behind it.

## Don't forget

- `AUTH_ENABLED=true` in production (it defaults on). Provide `BOOTSTRAP_API_KEY` or
  read the one-time minted key from the boot logs, then set it in the dashboard
  Settings (or `NEXT_PUBLIC_API_KEY`).
- `SANDBOX_RUNTIME=runsc` on the Linux node for the gVisor boundary.
- Lock the Docker socket down before external candidates (socket-proxy sidecar).
