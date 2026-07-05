"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { createSession, Template } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  templates: Template[];
  onCreated: (sessionId: string) => void;
}

export function CreateSandboxDialog({ open, onOpenChange, templates, onCreated }: Props) {
  const [questionId, setQuestionId] = useState("");
  const [candidateId, setCandidateId] = useState("");
  const [timeLimit, setTimeLimit] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Reset the form each time the dialog is (re)opened. This must depend ONLY on
  // `open` — `templates` is re-fetched every 3s (new array reference each poll),
  // and including it here would wipe the form mid-edit on every poll tick.
  useEffect(() => {
    if (open) {
      setQuestionId((prev) => prev || templatesRef.current[0]?.id || "");
      setCandidateId("");
      setTimeLimit("");
      setSubmitting(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Keep the latest templates available to the open-effect without making them a
  // dependency of it.
  const templatesRef = useRef(templates);
  templatesRef.current = templates;

  const limitNum = timeLimit.trim() === "" ? undefined : Number(timeLimit);
  const limitInvalid = limitNum !== undefined && (!Number.isFinite(limitNum) || limitNum <= 0);
  const valid = questionId !== "" && candidateId.trim() !== "" && !limitInvalid;

  async function handleSubmit() {
    if (!valid || submitting) return;
    setSubmitting(true);
    try {
      const result = await createSession({
        candidate_id: candidateId.trim(),
        question_id: questionId,
        time_limit_minutes: limitNum,
      });
      toast.success(`Sandbox created for ${candidateId.trim()}`);
      onOpenChange(false);
      onCreated(result.session_id);
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create sandbox</DialogTitle>
          <DialogDescription>
            Claim a warm container for a candidate. A live preview and terminal open immediately.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-1">
          <div className="grid gap-1.5">
            <Label htmlFor="sandbox-template">Template</Label>
            <Select
              value={questionId}
              onValueChange={(v) => setQuestionId((v as string) ?? "")}
            >
              <SelectTrigger id="sandbox-template" className="w-full">
                <SelectValue placeholder="Select a template" />
              </SelectTrigger>
              <SelectContent>
                {templates.map((t) => (
                  <SelectItem key={t.id} value={t.id}>
                    <span>
                      {t.title} · {t.id}
                      <span className="font-mono text-[10px] text-muted-foreground">
                        {t.kind} · {t.warm} warm
                      </span>
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              The question image the candidate works against.
            </p>
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="sandbox-candidate">Candidate ID</Label>
            <Input
              id="sandbox-candidate"
              value={candidateId}
              onChange={(e) => setCandidateId(e.target.value)}
              placeholder="alice@example.com"
            />
            <p className="text-xs text-muted-foreground">
              Identifier shown across sessions and the scorecard.
            </p>
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="sandbox-limit">Time limit (min)</Label>
            <Input
              id="sandbox-limit"
              type="number"
              min={1}
              value={timeLimit}
              onChange={(e) => setTimeLimit(e.target.value)}
              placeholder="90"
              aria-invalid={limitInvalid}
            />
            <p className="text-xs text-muted-foreground">
              Optional. Leave blank to use the template default.
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!valid || submitting}>
            {submitting ? "Creating…" : "Create"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
