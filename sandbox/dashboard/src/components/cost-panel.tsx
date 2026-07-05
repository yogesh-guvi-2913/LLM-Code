"use client";

import { getUsage } from "@/lib/api";
import { usePoll } from "@/lib/use-poll";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

// CostPanel surfaces GET /v1/usage — the "is it actually cheaper" number, computed
// from MEASURED live density. It deliberately shows a range: the conservative
// (OOM-safe) figure is the one to quote; the overcommit ceiling is an upper bound
// to validate under real load.
export function CostPanel() {
  const usage = usePoll(getUsage, 5000);
  const u = usage.data;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Cost & density</span>
          <span className="font-mono text-[11px] font-normal text-muted-foreground">
            {u ? `node ${u.cost_model.node_ram_gb}GB @ $${u.cost_model.node_usd_per_hour}/hr` : ""}
          </span>
        </CardTitle>
        <CardDescription>
          Billed sandbox-hours and $/sandbox-hr derived from measured live memory. Conservative is the
          number to quote.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!u ? (
          <p className="text-sm text-muted-foreground">
            {usage.error ? `unavailable — ${usage.error}` : "loading…"}
          </p>
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <Stat label="Billed sandbox-hrs" value={u.billed.sandbox_hours.toFixed(2)} />
              <Stat label="Active now" value={String(u.billed.active_now)} />
              <Stat
                label="Mem / sandbox"
                value={`${u.measured_density.measured_mem_per_sandbox_mb || 0} MB`}
                sub={`cfg ${u.measured_density.configured_mem_per_sandbox_mb} MB`}
              />
              <Stat label="Live containers" value={String(u.measured_density.live_containers)} />
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Bound
                tone="emerald"
                title="Conservative (quote this)"
                perNode={u.cost_model.conservative_sandboxes_per_node}
                usd={u.cost_model.conservative_usd_per_sandbox_hr}
              />
              <Bound
                tone="amber"
                title="Overcommit ceiling (validate)"
                perNode={u.cost_model.overcommit_ceiling_sandboxes_per_node}
                usd={u.cost_model.overcommit_ceiling_usd_per_sandbox_hr}
              />
            </div>
            <p className="text-[11px] leading-relaxed text-muted-foreground">{u.cost_model.note}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="font-mono text-lg font-semibold">{value}</div>
      {sub && <div className="font-mono text-[10px] text-muted-foreground">{sub}</div>}
    </div>
  );
}

function Bound({
  tone,
  title,
  perNode,
  usd,
}: {
  tone: "emerald" | "amber";
  title: string;
  perNode: number;
  usd: number;
}) {
  const cls =
    tone === "emerald"
      ? "border-emerald-500/30 bg-emerald-500/10"
      : "border-amber-500/30 bg-amber-500/10";
  return (
    <div className={`rounded-md border ${cls} px-3 py-2.5`}>
      <div className="text-xs text-muted-foreground">{title}</div>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="font-mono text-xl font-bold">${usd.toFixed(4)}</span>
        <span className="text-xs text-muted-foreground">/ sandbox-hr</span>
      </div>
      <div className="font-mono text-[11px] text-muted-foreground">{perNode} sandboxes / node</div>
    </div>
  );
}
