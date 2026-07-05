"use client";

import { getNodes, FleetNode } from "@/lib/api";
import { usePoll } from "@/lib/use-poll";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

// FleetTable shows GET /v1/nodes — one synthetic node in local mode, every live
// node-agent in cluster mode, with capacity, warm/active, and liveness.
export function FleetTable() {
  const nodes = usePoll(getNodes, 4000);
  const rows = nodes.data ?? [];
  const cluster = rows.some((n) => n.mode === "cluster");

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Fleet</span>
          <Badge variant="outline" className="font-mono text-[10px]">
            {cluster ? `${rows.length} node-agents` : "single node (local)"}
          </Badge>
        </CardTitle>
        <CardDescription>
          Sandbox runners and their capacity. In cluster mode each row is a node-agent reporting to Redis;
          in local mode it is this box.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Node</TableHead>
                <TableHead>Mode</TableHead>
                <TableHead>Memory</TableHead>
                <TableHead>Warm</TableHead>
                <TableHead>Active</TableHead>
                <TableHead>Liveness</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-sm text-muted-foreground">
                    {nodes.error ? `unavailable — ${nodes.error}` : "no live nodes"}
                  </TableCell>
                </TableRow>
              )}
              {rows.map((n) => (
                <TableRow key={n.id}>
                  <TableCell>
                    <div className="font-medium">{n.id}</div>
                    <div className="font-mono text-[11px] text-muted-foreground">{n.host}</div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="font-mono text-[10px]">
                      {n.mode}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <MemBar node={n} />
                  </TableCell>
                  <TableCell className="font-mono text-xs">{warmTotal(n)}</TableCell>
                  <TableCell className="font-mono text-xs">{n.active}</TableCell>
                  <TableCell>
                    <Liveness node={n} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}

function warmTotal(n: FleetNode) {
  return Object.values(n.warm ?? {}).reduce((a, b) => a + b, 0);
}

function MemBar({ node }: { node: FleetNode }) {
  if (!node.mem_total_mb) return <span className="font-mono text-[11px] text-muted-foreground">—</span>;
  const usedPct = Math.min(100, Math.round(((node.mem_total_mb - node.mem_free_mb) / node.mem_total_mb) * 100));
  return (
    <div className="w-40">
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary" style={{ width: `${usedPct}%` }} />
      </div>
      <div className="mt-1 font-mono text-[11px] text-muted-foreground">
        {Math.round(node.mem_free_mb / 1024)}G free / {Math.round(node.mem_total_mb / 1024)}G
      </div>
    </div>
  );
}

function Liveness({ node }: { node: FleetNode }) {
  if (node.mode === "local" || !node.last_seen_unix) {
    return <span className="font-mono text-[11px] text-muted-foreground">in-process</span>;
  }
  const ageSec = Math.max(0, Math.floor(Date.now() / 1000) - node.last_seen_unix);
  const ok = ageSec < 15;
  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-[11px]">
      <span className={`h-1.5 w-1.5 rounded-full ${ok ? "bg-emerald-500" : "bg-rose-500"}`} />
      {ageSec}s ago
    </span>
  );
}
