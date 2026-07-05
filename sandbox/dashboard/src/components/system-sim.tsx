"use client";

import { useEffect, useRef, useState } from "react";
import { Pause, Play, RotateCcw, Zap } from "lucide-react";

/**
 * A live simulation of the claim → run → submit → score pipeline.
 *
 * The point it makes visually: a warm pool turns demand into *instant* claims.
 * When the pool drains (a rush, an exam starting at 10:00), claims fall back to
 * cold-starts — the red, slow path. Toggle "Pre-warm" to raise the warm depth
 * ahead of the rush and watch the cold-starts disappear. That is the whole
 * idle-cost vs cold-start tradeoff, animated.
 *
 * No animation deps: a single requestAnimationFrame loop advances a mutable
 * sim held in a ref; React re-renders the SVG each frame off a tick counter.
 */

// ---- geometry ---------------------------------------------------------------
const VW = 1000;
const VH = 240;
const LANE = 130; // y of the main pipeline lane

type NodeKey = "spawn" | "orch" | "prov" | "pool" | "box" | "scorer" | "exit";
const NODE: Record<NodeKey, { x: number; y: number }> = {
  spawn: { x: 55, y: LANE },
  orch: { x: 215, y: LANE },
  prov: { x: 375, y: LANE },
  pool: { x: 540, y: LANE },
  box: { x: 715, y: LANE },
  scorer: { x: 880, y: LANE },
  exit: { x: 975, y: LANE },
};

// ---- timings (ms) -----------------------------------------------------------
const TRAVEL = 750; // per pipeline segment
const RUN_MS = 2600; // candidate codes in the sandbox
const SCORE_MS = 1100; // scorer runs the hidden tests
const BOOT_MS = 2200; // a warm container booting (background refill)
const COLD_MS = 4200; // cold-start penalty when the pool is empty

const MODES = {
  calm: { label: "Calm", every: 2600 },
  rush: { label: "Rush", every: 950 },
  exam: { label: "Exam start", every: 360 },
} as const;
type Mode = keyof typeof MODES;

type Stage =
  | "toOrch"
  | "toProv"
  | "toPool"
  | "coldwait"
  | "toBox"
  | "running"
  | "toScorer"
  | "scored"
  | "leaving";

interface Cand {
  id: number;
  stage: Stage;
  t: number; // 0..1 within a travel stage, or ms remaining for dwell stages
  jitter: number;
  cold: boolean;
  score: number | null;
}

interface Sim {
  cands: Cand[];
  warm: number; // ready-to-claim containers
  boots: number[]; // remaining ms for each background-booting container
  target: number; // desired warm depth
  spawnAcc: number;
  nextId: number;
  claims: number;
  colds: number;
  mode: Mode;
}

const STAGE_FROM_TO: Partial<Record<Stage, [NodeKey, NodeKey]>> = {
  toOrch: ["spawn", "orch"],
  toProv: ["orch", "prov"],
  toPool: ["prov", "pool"],
  toBox: ["pool", "box"],
  toScorer: ["box", "scorer"],
  leaving: ["scorer", "exit"],
};
const STAGE_AT: Partial<Record<Stage, NodeKey>> = {
  coldwait: "pool",
  running: "box",
  scored: "scorer",
};

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

function candPos(c: Cand): { x: number; y: number } {
  const seg = STAGE_FROM_TO[c.stage];
  if (seg) {
    const a = NODE[seg[0]];
    const b = NODE[seg[1]];
    return { x: lerp(a.x, b.x, c.t), y: lerp(a.y, b.y, c.t) + c.jitter };
  }
  const at = STAGE_AT[c.stage]!;
  return { x: NODE[at].x, y: NODE[at].y + c.jitter };
}

function freshSim(mode: Mode, target: number): Sim {
  return {
    cands: [],
    warm: target,
    boots: [],
    target,
    spawnAcc: 0,
    nextId: 1,
    claims: 0,
    colds: 0,
    mode,
  };
}

function step(s: Sim, dt: number) {
  // spawn
  s.spawnAcc += dt;
  const every = MODES[s.mode].every;
  while (s.spawnAcc >= every && s.cands.length < 16) {
    s.spawnAcc -= every;
    s.cands.push({
      id: s.nextId++,
      stage: "toOrch",
      t: 0,
      jitter: (((s.nextId * 53) % 36) - 18) * 0.7,
      cold: false,
      score: null,
    });
  }

  // background refill toward target
  if (s.warm + s.boots.length < s.target) s.boots.push(BOOT_MS);
  for (let i = s.boots.length - 1; i >= 0; i--) {
    s.boots[i] -= dt;
    if (s.boots[i] <= 0) {
      s.boots.splice(i, 1);
      if (s.warm < s.target) s.warm++;
    }
  }

  const advanceTravel = (c: Cand, next: Stage) => {
    c.t += dt / TRAVEL;
    if (c.t >= 1) {
      c.t = 0;
      c.stage = next;
      return true;
    }
    return false;
  };

  for (let i = s.cands.length - 1; i >= 0; i--) {
    const c = s.cands[i];
    switch (c.stage) {
      case "toOrch":
        advanceTravel(c, "toProv");
        break;
      case "toProv":
        advanceTravel(c, "toPool");
        break;
      case "toPool":
        if (advanceTravel(c, "toBox")) {
          // arrived at the pool — try to claim a warm container
          if (s.warm > 0) {
            s.warm--;
            s.claims++;
            c.cold = false;
          } else {
            s.colds++;
            c.cold = true;
            c.stage = "coldwait";
            c.t = COLD_MS;
          }
        }
        break;
      case "coldwait":
        c.t -= dt;
        if (c.t <= 0) {
          c.t = 0;
          c.stage = "toBox";
        }
        break;
      case "toBox":
        if (advanceTravel(c, "running")) c.t = RUN_MS;
        break;
      case "running":
        c.t -= dt;
        if (c.t <= 0) {
          c.t = 0;
          c.stage = "toScorer";
        }
        break;
      case "toScorer":
        if (advanceTravel(c, "scored")) {
          c.t = SCORE_MS;
          c.score = c.id % 3 === 0 ? 0 : 100; // most pass, some fail
        }
        break;
      case "scored":
        c.t -= dt;
        if (c.t <= 0) {
          c.t = 0;
          c.stage = "leaving";
        }
        break;
      case "leaving":
        if (advanceTravel(c, "leaving")) s.cands.splice(i, 1);
        break;
    }
  }
}

// ---- view -------------------------------------------------------------------
const C = {
  card: "var(--card)",
  border: "var(--border)",
  muted: "var(--muted-foreground)",
  fg: "var(--foreground)",
  emerald: "#10b981",
  sky: "#0ea5e9",
  amber: "#f59e0b",
  red: "#ef4444",
};

function Box({
  k,
  w = 96,
  h = 58,
  title,
  sub,
  accent,
}: {
  k: NodeKey;
  w?: number;
  h?: number;
  title: string;
  sub?: string;
  accent?: string;
}) {
  const { x, y } = NODE[k];
  return (
    <g>
      <rect
        x={x - w / 2}
        y={y - h / 2}
        width={w}
        height={h}
        rx={10}
        fill={C.card}
        stroke={accent ?? C.border}
        strokeWidth={accent ? 1.5 : 1}
      />
      <text
        x={x}
        y={sub ? y - 4 : y + 4}
        textAnchor="middle"
        fontSize={13}
        fontWeight={600}
        fill={C.fg}
      >
        {title}
      </text>
      {sub && (
        <text x={x} y={y + 13} textAnchor="middle" fontSize={10} fill={C.muted}>
          {sub}
        </text>
      )}
    </g>
  );
}

function Edge({ from, to, label }: { from: NodeKey; to: NodeKey; label: string }) {
  const a = NODE[from];
  const b = NODE[to];
  const mx = (a.x + b.x) / 2;
  return (
    <g>
      <line
        x1={a.x + 50}
        y1={a.y}
        x2={b.x - 50}
        y2={b.y}
        stroke={C.border}
        strokeWidth={1.5}
        strokeDasharray="4 5"
        className="sim-flow"
      />
      <text x={mx} y={a.y - 12} textAnchor="middle" fontSize={9.5} fill={C.muted}>
        {label}
      </text>
    </g>
  );
}

interface View {
  cands: Cand[];
  warm: number;
  target: number;
  boots: number;
  claims: number;
  colds: number;
}
function snap(s: Sim): View {
  return {
    cands: s.cands.map((c) => ({ ...c })),
    warm: s.warm,
    target: s.target,
    boots: s.boots.length,
    claims: s.claims,
    colds: s.colds,
  };
}

export function SystemSim() {
  // The mutable sim lives in a ref (mutated by the timer); render never reads
  // it directly. Each tick we publish an immutable snapshot into `view`, so the
  // render path only ever reads React state.
  const sim = useRef<Sim>(freshSim("calm", 4));
  const [view, setView] = useState<View>(() => snap(freshSim("calm", 4)));
  const [playing, setPlaying] = useState(true);
  const [mode, setMode] = useState<Mode>("calm");
  const [prewarm, setPrewarm] = useState(false);
  const last = useRef<number | null>(null);

  // keep sim params in sync with controls
  useEffect(() => {
    sim.current.mode = mode;
  }, [mode]);
  useEffect(() => {
    sim.current.target = prewarm ? 8 : 4;
  }, [prewarm]);

  // A timer drives the sim — robust whether the tab is visible or hidden
  // (requestAnimationFrame pauses in background tabs; setInterval does not).
  // dt is measured from a real clock and clamped, so motion stays time-correct.
  useEffect(() => {
    if (!playing) {
      last.current = null;
      return;
    }
    last.current = performance.now();
    const h = setInterval(() => {
      const now = performance.now();
      let dt = now - (last.current ?? now);
      last.current = now;
      if (dt > 80) dt = 80; // clamp tab-switch / throttle jumps
      step(sim.current, dt);
      setView(snap(sim.current));
    }, 1000 / 30);
    return () => clearInterval(h);
  }, [playing]);

  const s = view;
  const active = s.cands.filter((c) =>
    ["toBox", "running", "toScorer", "scored"].includes(c.stage),
  ).length;
  const coldNow = s.cands.some((c) => c.stage === "coldwait");
  const slots = Math.max(s.target, 4);

  let status: { text: string; color: string };
  if (coldNow)
    status = { text: "Pool empty — cold-starting (~4s latency)", color: C.red };
  else if (s.warm === 0)
    status = { text: "Pool drained — next claim will be cold", color: C.amber };
  else if (s.warm < s.target)
    status = { text: "Refilling warm pool in the background…", color: C.amber };
  else status = { text: "Warm pool full — every claim is instant", color: C.emerald };

  const reset = () => {
    sim.current = freshSim(mode, prewarm ? 8 : 4);
    last.current = null;
    setView(snap(sim.current));
  };

  return (
    <div className="space-y-4">
      {/* controls */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => setPlaying((p) => !p)}
          className="inline-flex items-center gap-1.5 rounded-md border bg-card px-3 py-1.5 text-sm font-medium hover:bg-muted/50"
        >
          {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          {playing ? "Pause" : "Play"}
        </button>
        <button
          onClick={reset}
          className="inline-flex items-center gap-1.5 rounded-md border bg-card px-3 py-1.5 text-sm font-medium hover:bg-muted/50"
        >
          <RotateCcw className="h-4 w-4" />
          Reset
        </button>

        <div className="mx-1 inline-flex overflow-hidden rounded-md border">
          {(Object.keys(MODES) as Mode[]).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={
                "px-3 py-1.5 text-sm font-medium transition-colors " +
                (mode === m
                  ? "bg-primary text-primary-foreground"
                  : "bg-card hover:bg-muted/50")
              }
            >
              {MODES[m].label}
            </button>
          ))}
        </div>

        <button
          onClick={() => setPrewarm((p) => !p)}
          className={
            "inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm font-medium transition-colors " +
            (prewarm
              ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
              : "bg-card hover:bg-muted/50")
          }
        >
          <Zap className="h-4 w-4" />
          Pre-warm {prewarm ? "ON" : "OFF"}
        </button>

        <span
          className="ml-auto inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium"
          style={{ color: status.color, borderColor: status.color + "55" }}
        >
          <span
            className="h-2 w-2 rounded-full"
            style={{ background: status.color }}
          />
          {status.text}
        </span>
      </div>

      {/* HUD */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Warm ready" value={`${s.warm} / ${s.target}`} hint="instant claims" />
        <Stat label="Active sandboxes" value={active} hint="running now" />
        <Stat label="Instant claims" value={s.claims} hint="served from warm pool" />
        <Stat
          label="Cold starts"
          value={s.colds}
          hint="paid full boot latency"
          danger={s.colds > 0}
        />
      </div>

      {/* scene */}
      <div className="overflow-hidden rounded-xl border bg-gradient-to-b from-muted/30 to-transparent">
        <svg viewBox={`0 0 ${VW} ${VH}`} className="w-full" role="img">
          {/* edges */}
          <Edge from="spawn" to="orch" label="session token" />
          <Edge from="orch" to="prov" label="claim" />
          <Edge from="prov" to="pool" label="pick warm" />
          <Edge from="pool" to="box" label="exec · preview" />
          <Edge from="box" to="scorer" label="submit" />
          <Edge from="scorer" to="exit" label="score" />

          {/* nodes */}
          <Box k="spawn" title="Candidates" sub="arriving" w={88} />
          <Box k="orch" title="Orchestrator" sub="routes" />
          <Box k="prov" title="Provisioner" sub="seam" />
          <Box k="box" title="Sandbox" sub="gVisor" accent={active ? C.emerald : undefined} />
          <Box
            k="scorer"
            title="Scorer"
            sub="--net none"
            accent={s.cands.some((c) => c.stage === "scored") ? C.sky : undefined}
          />

          {/* warm pool with slots */}
          <PoolNode warm={s.warm} booting={s.boots} slots={slots} cold={coldNow} />

          {/* exit marker */}
          <text x={NODE.exit.x} y={LANE + 4} textAnchor="middle" fontSize={11} fill={C.muted}>
            done
          </text>

          {/* candidates */}
          {s.cands.map((c) => {
            const p = candPos(c);
            const color =
              c.stage === "coldwait"
                ? C.red
                : c.score === 100
                  ? C.emerald
                  : c.score === 0
                    ? C.red
                    : c.cold
                      ? C.amber
                      : C.sky;
            return (
              <g key={c.id}>
                {c.stage === "coldwait" && (
                  <circle
                    cx={p.x}
                    cy={p.y}
                    r={16}
                    fill="none"
                    stroke={C.red}
                    strokeWidth={1.5}
                    className="sim-pulse"
                  />
                )}
                {c.stage === "running" && (
                  <circle cx={p.x} cy={p.y} r={14} fill={C.emerald} opacity={0.18} className="sim-pulse" />
                )}
                <circle cx={p.x} cy={p.y} r={9} fill={color} />
                {c.score != null && (c.stage === "scored" || c.stage === "leaving") && (
                  <text
                    x={p.x}
                    y={p.y - 14}
                    textAnchor="middle"
                    fontSize={11}
                    fontWeight={700}
                    fill={color}
                  >
                    {c.score}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      <p className="text-sm text-muted-foreground">
        Hit <span className="font-medium text-foreground">Exam start</span> and watch the warm pool
        drain — claims fall back to red <span className="font-medium text-foreground">cold-starts</span>.
        Now flip <span className="font-medium text-foreground">Pre-warm ON</span> (scheduled scaling
        ahead of 10:00) and they vanish: deeper warm pool absorbs the spike, every claim stays instant.
        That is the idle-cost vs cold-start tradeoff — the entire reason this exists.
      </p>
    </div>
  );
}

function PoolNode({
  warm,
  booting,
  slots,
  cold,
}: {
  warm: number;
  booting: number;
  slots: number;
  cold: boolean;
}) {
  const { x, y } = NODE.pool;
  const cell = 13;
  const gap = 4;
  const cols = Math.min(slots, 4);
  const rows = Math.ceil(slots / cols);
  const gridW = cols * cell + (cols - 1) * gap;
  const gridH = rows * cell + (rows - 1) * gap;
  const x0 = x - gridW / 2;
  const y0 = y - gridH / 2;
  return (
    <g>
      <rect
        x={x - 60}
        y={y - 42}
        width={120}
        height={84}
        rx={10}
        fill={C.card}
        stroke={cold ? C.red : C.border}
        strokeWidth={cold ? 1.5 : 1}
      />
      <text x={x} y={y - 30} textAnchor="middle" fontSize={12} fontWeight={600} fill={C.fg}>
        Warm pool
      </text>
      {Array.from({ length: slots }).map((_, i) => {
        const r = Math.floor(i / cols);
        const cI = i % cols;
        const cx = x0 + cI * (cell + gap);
        const cy = y0 + r * (cell + gap) + 6;
        const filled = i < warm;
        const isBooting = !filled && i < warm + booting;
        return (
          <rect
            key={i}
            x={cx}
            y={cy}
            width={cell}
            height={cell}
            rx={3}
            fill={filled ? C.emerald : isBooting ? C.amber : "transparent"}
            stroke={filled ? C.emerald : isBooting ? C.amber : C.border}
            strokeWidth={1}
            strokeDasharray={filled || isBooting ? "0" : "2 2"}
            className={isBooting ? "sim-pulse" : undefined}
          />
        );
      })}
    </g>
  );
}

function Stat({
  label,
  value,
  hint,
  danger,
}: {
  label: string;
  value: number | string;
  hint: string;
  danger?: boolean;
}) {
  return (
    <div className="rounded-lg border bg-card p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div
        className={
          "text-2xl font-bold tabular-nums " + (danger ? "text-red-500" : "")
        }
      >
        {value}
      </div>
      <div className="text-[11px] text-muted-foreground">{hint}</div>
    </div>
  );
}
