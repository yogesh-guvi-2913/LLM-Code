import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Session } from "@/lib/api";
import { StatusBadge } from "./status-badge";

function initials(s: string) {
  const cleaned = s.replace(/[^a-zA-Z0-9]/g, "");
  return (cleaned.slice(0, 2) || "??").toUpperCase();
}

export function RecentSessions({
  rows,
  onSelect,
}: {
  rows: Session[];
  onSelect?: (id: string) => void;
}) {
  if (rows.length === 0)
    return <p className="text-sm text-muted-foreground">No sessions yet.</p>;

  return (
    <div className="space-y-6">
      {rows.slice(0, 6).map((s) => (
        <div
          key={s.id}
          onClick={() => onSelect?.(s.id)}
          className={
            onSelect
              ? "-mx-2 flex cursor-pointer items-center rounded-md px-2 py-1 hover:bg-muted/50"
              : "flex items-center"
          }
        >
          <Avatar className="h-9 w-9">
            <AvatarFallback className="text-xs">{initials(s.candidate_id)}</AvatarFallback>
          </Avatar>
          <div className="ml-4 space-y-1">
            <p className="text-sm font-medium leading-none">{s.candidate_id}</p>
            <p className="text-xs text-muted-foreground">
              {s.question_id} · <StatusBadge status={s.status} />
            </p>
          </div>
          <div className="ml-auto text-sm font-medium">
            {s.score != null && s.max_score ? (
              <span>
                {s.score}
                <span className="text-muted-foreground">/{s.max_score}</span>
              </span>
            ) : s.submission_status === "scoring" ? (
              <span className="text-primary">scoring…</span>
            ) : (
              <span className="text-muted-foreground">—</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
