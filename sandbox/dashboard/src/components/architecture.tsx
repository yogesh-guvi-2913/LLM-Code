"use client";

import {
  Boxes,
  Database,
  Gauge,
  KeyRound,
  Layers,
  MonitorPlay,
  Network,
  Server,
  ShieldCheck,
  TerminalSquare,
  Workflow,
} from "lucide-react";
import { SystemSim } from "./system-sim";

/**
 * "How it works" — a live simulation of the pipeline, a numbered request
 * lifecycle, and a one-line reference for every module.
 */

const OP = "operator"; // operator plane — API key (you / the dashboard)
const CAND = "candidate"; // candidate plane — session token (the student)

function PlaneDot({ plane }: { plane: typeof OP | typeof CAND }) {
  return (
    <span
      className={
        "inline-block h-2 w-2 rounded-full " +
        (plane === OP ? "bg-sky-500" : "bg-emerald-500")
      }
    />
  );
}

const LIFECYCLE = [
  {
    n: 1,
    title: "Claim",
    body: "Warm pool hands over a ready container instantly. If none, it cold-starts one and refills the pool.",
  },
  {
    n: 2,
    title: "Code",
    body: "Playground writes files straight into the running sandbox via docker exec — no image rebuild.",
  },
  {
    n: 3,
    title: "Preview",
    body: "The live dev server is exposed on a wildcard subdomain, authed by the host token in the URL.",
  },
  {
    n: 4,
    title: "Submit",
    body: "Source is snapshotted to a tar and fed to an isolated scorer container with --network none.",
  },
  {
    n: 5,
    title: "Score",
    body: "Scorer runs the hidden test harness, emits a JSON score, and the result is persisted to Postgres.",
  },
];

const MODULES = [
  {
    icon: MonitorPlay,
    name: "Operator console",
    plane: OP,
    line: "This dashboard. Manages templates, sessions, fleet & cost. Authed by an org API key (hyk_).",
  },
  {
    icon: TerminalSquare,
    name: "Candidate playground",
    plane: CAND,
    line: "Monaco IDE the student embeds. Edit, run, preview, submit. Authed only by a per-session token.",
  },
  {
    icon: Workflow,
    name: "Orchestrator",
    line: "Go control plane. Splits operator vs candidate routes, owns session lifecycle, exports metrics.",
  },
  {
    icon: Layers,
    name: "Provisioner (seam)",
    line: "One interface, two backends. Same control-plane code runs single-node or across a cluster.",
  },
  {
    icon: Boxes,
    name: "Warm pool",
    line: "Pre-booted containers kept ready so a claim is instant instead of paying cold-start latency.",
  },
  {
    icon: Server,
    name: "Node-agents",
    line: "One per box in cluster mode. Run the local pool, heartbeat capacity to Redis, take scheduled work.",
  },
  {
    icon: Network,
    name: "Cluster registry",
    line: "Redis. Node liveness via TTL heartbeats + warm depth. PickNode prefers warm, else bin-packs by free RAM.",
  },
  {
    icon: Database,
    name: "Store",
    line: "Postgres. Orgs, API keys, sessions and submissions — the source of truth that survives a restart.",
  },
  {
    icon: ShieldCheck,
    name: "Runtime",
    line: "Docker + gVisor (runsc). Cap-drop ALL, read-only rootfs, no-new-privileges — hostile-code safe.",
  },
  {
    icon: KeyRound,
    name: "Scorer",
    line: "Throwaway container with --network none and a pids/mem cap. Runs hidden tests, can't phone home.",
  },
  {
    icon: MonitorPlay,
    name: "Preview",
    line: "Wildcard *.preview host. The leftmost label is the token, so each sandbox gets an isolated origin.",
  },
  {
    icon: Gauge,
    name: "Cost model",
    line: "Density from measured docker-stats memory. Reports a range: OOM-safe floor → overcommit ceiling.",
  },
];

export function Architecture() {
  return (
    <div className="space-y-8">
      {/* Live simulation — the hero */}
      <div>
        <h3 className="mb-1 text-lg font-semibold">Live simulation</h3>
        <p className="mb-4 text-sm text-muted-foreground">
          Candidates flow through the real pipeline. Drive the load and watch the warm pool
          decide between instant claims and cold-starts.
        </p>
        <SystemSim />
      </div>

      {/* Lifecycle */}
      <div>
        <h3 className="mb-1 text-lg font-semibold">Request lifecycle</h3>
        <p className="mb-4 text-sm text-muted-foreground">
          What happens between a student opening the IDE and seeing a score.
        </p>
        <div className="grid gap-3 md:grid-cols-5">
          {LIFECYCLE.map((s) => (
            <div key={s.n} className="rounded-lg border bg-card p-3">
              <div className="mb-2 flex h-6 w-6 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
                {s.n}
              </div>
              <div className="text-sm font-semibold">{s.title}</div>
              <p className="mt-1 text-xs leading-snug text-muted-foreground">
                {s.body}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Module reference */}
      <div>
        <h3 className="mb-1 text-lg font-semibold">Every module</h3>
        <p className="mb-4 text-sm text-muted-foreground">
          One line each — what it is and why it exists.
        </p>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {MODULES.map((m) => (
            <div
              key={m.name}
              className="flex flex-col gap-1.5 rounded-lg border bg-card p-3"
            >
              <div className="flex items-center gap-2">
                <m.icon className="h-4 w-4 text-foreground/70" />
                <span className="text-sm font-semibold">{m.name}</span>
                {m.plane && <PlaneDot plane={m.plane as typeof OP} />}
              </div>
              <p className="text-xs leading-snug text-muted-foreground">
                {m.line}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
