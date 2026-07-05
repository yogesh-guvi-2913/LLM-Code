import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { SessionStatus } from "@/lib/api";

const MAP: Record<string, string> = {
  ACTIVE: "border-emerald-500/30 bg-emerald-500/10 text-emerald-500",
  SUBMITTED: "border-primary/30 bg-primary/10 text-primary",
  TIMED_OUT: "border-amber-500/30 bg-amber-500/10 text-amber-500",
  DESTROYED: "border-border bg-muted text-muted-foreground",
};

export function StatusBadge({ status }: { status: SessionStatus | string }) {
  return (
    <Badge variant="outline" className={cn("font-mono text-[10px]", MAP[status] ?? MAP.DESTROYED)}>
      {status}
    </Badge>
  );
}

export function StateBadge({ active }: { active: boolean }) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "gap-1.5",
        active
          ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-500"
          : "border-amber-500/30 bg-amber-500/10 text-amber-500"
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", active ? "bg-emerald-500" : "bg-amber-500")} />
      {active ? "Active" : "Draining"}
    </Badge>
  );
}
