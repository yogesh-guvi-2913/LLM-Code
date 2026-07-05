"use client";

import { useState } from "react";
import { CalendarClock, Flame, Plus, X } from "lucide-react";
import { toast } from "sonner";
import {
  AssessmentWindow,
  cancelWindow,
  createWindow,
  getTemplates,
  getWindows,
  Template,
  WindowPhase,
} from "@/lib/api";
import { usePoll } from "@/lib/use-poll";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const PHASE: Record<WindowPhase, { label: string; cls: string }> = {
  scheduled: { label: "Scheduled", cls: "border-muted-foreground/30 text-muted-foreground" },
  prewarming: { label: "Pre-warming", cls: "border-amber-500/40 text-amber-500" },
  active: { label: "Active", cls: "border-emerald-500/40 text-emerald-500" },
  done: { label: "Done", cls: "border-muted-foreground/20 text-muted-foreground/70" },
  canceled: { label: "Canceled", cls: "border-muted-foreground/20 text-muted-foreground/50 line-through" },
};

// datetime-local gives "YYYY-MM-DDTHH:mm" in local time; the API wants RFC3339.
function toRFC3339(local: string): string {
  return new Date(local).toISOString();
}
function fmt(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
// default start: next half hour, +1h; end +2h
function defaultStart(): string {
  const d = new Date(Date.now() + 60 * 60 * 1000);
  d.setMinutes(d.getMinutes() < 30 ? 30 : 0, 0, 0);
  if (d.getMinutes() === 0) d.setHours(d.getHours() + 1);
  return localValue(d);
}
function localValue(d: Date): string {
  const off = d.getTimezoneOffset();
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 16);
}

export function Schedule() {
  const windows = usePoll(() => getWindows(true), 2000);
  const templates = usePoll(getTemplates, 8000);
  const tmpls = templates.data ?? [];

  const data = windows.data;
  const rows = data?.windows ?? [];
  const desired = data?.desired_warm_now ?? {};
  const live = rows.filter((w) => w.phase !== "done" && w.phase !== "canceled");
  const history = rows.filter((w) => w.phase === "done" || w.phase === "canceled");

  async function onCancel(id: string) {
    try {
      await cancelWindow(id);
      toast.success("Window canceled");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <BookingForm templates={tmpls} />

      {/* Planner state: what's warming right now because of a window */}
      {Object.keys(desired).length > 0 && (
        <Card className="border-amber-500/30 bg-amber-500/[0.04]">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <Flame className="h-4 w-4 text-amber-500" />
              Pre-warming now
            </CardTitle>
            <CardDescription>
              The planner is holding these warm floors right now to cover open windows.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {Object.entries(desired).map(([q, n]) => (
              <span
                key={q}
                className="inline-flex items-center gap-2 rounded-md border border-amber-500/40 bg-background px-3 py-1.5 text-sm"
              >
                <span className="font-mono font-medium">{q}</span>
                <span className="text-muted-foreground">warm floor →</span>
                <span className="font-bold tabular-nums text-amber-500">{n}</span>
              </span>
            ))}
          </CardContent>
        </Card>
      )}

      <WindowTable
        title="Upcoming & active"
        empty="No windows booked. Book one above to pre-warm a template ahead of an assessment."
        rows={live}
        onCancel={onCancel}
        cancelable
      />

      {history.length > 0 && (
        <WindowTable title="History" empty="" rows={history} onCancel={onCancel} />
      )}
    </div>
  );
}

function BookingForm({ templates }: { templates: Template[] }) {
  const [questionId, setQuestionId] = useState("");
  const [label, setLabel] = useState("");
  const [seats, setSeats] = useState("25");
  const [lead, setLead] = useState("10");
  const [startsAt, setStartsAt] = useState(defaultStart);
  const [endsAt, setEndsAt] = useState(() => {
    const d = new Date(Date.now() + 3 * 60 * 60 * 1000);
    return localValue(d);
  });
  const [busy, setBusy] = useState(false);

  const qid = questionId || templates[0]?.id || "";
  const seatsNum = Number(seats);
  const leadNum = Number(lead);
  const valid =
    qid !== "" &&
    Number.isFinite(seatsNum) &&
    seatsNum >= 1 &&
    seatsNum <= 200 &&
    Number.isFinite(leadNum) &&
    leadNum >= 0 &&
    startsAt !== "" &&
    endsAt !== "" &&
    new Date(endsAt) > new Date(startsAt);

  async function book() {
    if (!valid || busy) return;
    setBusy(true);
    try {
      await createWindow({
        question_id: qid,
        label: label.trim(),
        seats: seatsNum,
        lead_minutes: leadNum,
        starts_at: toRFC3339(startsAt),
        ends_at: toRFC3339(endsAt),
      });
      toast.success(`Window booked — ${qid} pre-warms ${leadNum} min ahead`);
      setLabel("");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <CalendarClock className="h-4 w-4" />
          Book a pre-warm window
        </CardTitle>
        <CardDescription>
          Reserve warm capacity for an assessment. The planner raises the template’s warm floor{" "}
          <span className="font-medium text-foreground">lead</span> minutes before the start and
          restores it after — so candidates never hit a cold-start at 10:00.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <div className="grid gap-1.5">
            <Label htmlFor="w-template">Template</Label>
            <Select value={qid} onValueChange={(v) => setQuestionId((v as string) ?? "")}>
              <SelectTrigger id="w-template" className="w-full">
                <SelectValue placeholder="Select a template" />
              </SelectTrigger>
              <SelectContent>
                {templates.map((t) => (
                  <SelectItem key={t.id} value={t.id}>
                    {t.title} · {t.id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="w-seats">Seats (warm sandboxes)</Label>
            <Input
              id="w-seats"
              type="number"
              min={1}
              max={200}
              value={seats}
              onChange={(e) => setSeats(e.target.value)}
            />
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="w-lead">Lead (min before start)</Label>
            <Input
              id="w-lead"
              type="number"
              min={0}
              max={120}
              value={lead}
              onChange={(e) => setLead(e.target.value)}
            />
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="w-start">Starts</Label>
            <Input
              id="w-start"
              type="datetime-local"
              value={startsAt}
              onChange={(e) => setStartsAt(e.target.value)}
            />
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="w-end">Ends</Label>
            <Input
              id="w-end"
              type="datetime-local"
              value={endsAt}
              onChange={(e) => setEndsAt(e.target.value)}
            />
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="w-label">Label (optional)</Label>
            <Input
              id="w-label"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Frontend cohort A"
            />
          </div>
        </div>

        <div className="mt-4 flex justify-end">
          <Button onClick={book} disabled={!valid || busy}>
            <Plus className="mr-2 h-4 w-4" />
            {busy ? "Booking…" : "Book window"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function WindowTable({
  title,
  empty,
  rows,
  onCancel,
  cancelable,
}: {
  title: string;
  empty: string;
  rows: AssessmentWindow[];
  onCancel: (id: string) => void;
  cancelable?: boolean;
}) {
  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold text-muted-foreground">{title}</h3>
      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Template</TableHead>
              <TableHead>Label</TableHead>
              <TableHead className="text-right">Seats</TableHead>
              <TableHead className="text-right">Lead</TableHead>
              <TableHead>Window</TableHead>
              <TableHead>Phase</TableHead>
              {cancelable && <TableHead className="w-10" />}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={cancelable ? 7 : 6} className="py-8 text-center text-sm text-muted-foreground">
                  {empty}
                </TableCell>
              </TableRow>
            ) : (
              rows.map((w) => {
                const p = PHASE[w.phase];
                return (
                  <TableRow key={w.id}>
                    <TableCell className="font-mono text-xs">{w.question_id}</TableCell>
                    <TableCell className="text-sm">{w.label || "—"}</TableCell>
                    <TableCell className="text-right font-medium tabular-nums">{w.seats}</TableCell>
                    <TableCell className="text-right tabular-nums text-muted-foreground">
                      {w.lead_minutes}m
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {fmt(w.starts_at)} → {fmt(w.ends_at)}
                    </TableCell>
                    <TableCell>
                      <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${p.cls}`}>
                        {p.label}
                      </span>
                    </TableCell>
                    {cancelable && (
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-muted-foreground hover:text-destructive"
                          onClick={() => onCancel(w.id)}
                          aria-label="Cancel window"
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    )}
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
