import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { Template } from "@/lib/api";
import { StateBadge } from "./status-badge";
import { ScaleCell } from "./scale-cell";

function langClass(lang: string) {
  return /python|flask/i.test(lang)
    ? "border-amber-500/30 bg-amber-500/10 text-amber-500"
    : "border-emerald-500/30 bg-emerald-500/10 text-emerald-500";
}

export function TemplatesTable({ rows }: { rows: Template[] }) {
  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Image</TableHead>
            <TableHead>Resources</TableHead>
            <TableHead>Warm pool</TableHead>
            <TableHead>Scale</TableHead>
            <TableHead>State</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((t) => {
            const pct = t.min_warm ? Math.min(100, Math.round((t.warm / t.min_warm) * 100)) : 0;
            return (
              <TableRow key={t.id}>
                <TableCell>
                  <div className="flex items-center gap-2.5">
                    <span className="font-medium">{t.title}</span>
                    <Badge variant="outline" className={cn("font-mono text-[10px]", langClass(t.language))}>
                      {t.language}
                    </Badge>
                  </div>
                  <div className="mt-0.5 font-mono text-[11px] text-muted-foreground">
                    {t.id} · {t.slug}
                  </div>
                </TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">{t.image}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-1.5 font-mono text-[11px] text-muted-foreground">
                    <Spec>{t.vcpu} vCPU</Spec>
                    <Spec>{t.memory_mb} MB</Spec>
                    <Spec>{t.pids_limit} pids</Spec>
                  </div>
                </TableCell>
                <TableCell className="w-48">
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                    <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
                  </div>
                  <div className="mt-1.5 font-mono text-[11px] text-muted-foreground">
                    {t.warm} / {t.min_warm} min
                  </div>
                </TableCell>
                <TableCell>
                  <ScaleCell template={t} />
                </TableCell>
                <TableCell>
                  <StateBadge active={t.warm > 0} />
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

function Spec({ children }: { children: React.ReactNode }) {
  return <span className="rounded border bg-muted px-1.5 py-0.5">{children}</span>;
}
