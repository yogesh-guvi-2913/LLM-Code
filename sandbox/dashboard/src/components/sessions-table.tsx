import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Session } from "@/lib/api";
import { relTime, shortId } from "@/lib/format";
import { StatusBadge } from "./status-badge";

function Score({ s }: { s: Session }) {
  if (s.score != null && s.max_score) {
    const pct = Math.round((s.score / s.max_score) * 100);
    return (
      <div className="flex items-center gap-2">
        <div className="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
        </div>
        <span className="font-mono text-xs text-muted-foreground">
          {s.score}/{s.max_score}
        </span>
      </div>
    );
  }
  if (s.submission_status === "scoring")
    return <span className="font-mono text-xs text-primary">scoring…</span>;
  return <span className="font-mono text-xs text-muted-foreground">—</span>;
}

export function SessionsTable({
  rows,
  onSelect,
}: {
  rows: Session[];
  onSelect?: (id: string) => void;
}) {
  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Session</TableHead>
            <TableHead>Candidate</TableHead>
            <TableHead>Template</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Score</TableHead>
            <TableHead>Created</TableHead>
            <TableHead>Expires</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.length === 0 && (
            <TableRow>
              <TableCell colSpan={7} className="h-24 text-center text-muted-foreground">
                No sessions yet.
              </TableCell>
            </TableRow>
          )}
          {rows.map((s) => (
            <TableRow
              key={s.id}
              onClick={() => onSelect?.(s.id)}
              className={onSelect ? "cursor-pointer" : undefined}
            >
              <TableCell className="font-mono text-xs">{shortId(s.id)}</TableCell>
              <TableCell className="font-medium">{s.candidate_id}</TableCell>
              <TableCell className="font-mono text-xs text-muted-foreground">{s.question_id}</TableCell>
              <TableCell>
                <StatusBadge status={s.status} />
              </TableCell>
              <TableCell>
                <Score s={s} />
              </TableCell>
              <TableCell className="font-mono text-xs text-muted-foreground">{relTime(s.created_at)}</TableCell>
              <TableCell className="font-mono text-xs text-muted-foreground">{relTime(s.expires_at)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
