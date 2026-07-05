"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Code2 } from "lucide-react";
import { toast } from "sonner";
import {
  destroySession,
  getSession,
  playgroundHref,
  SessionDetail,
  submitSession,
  terminalSrc,
} from "@/lib/api";
import { relTime, shortId } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { StatusBadge } from "./status-badge";

interface Props {
  sessionId: string | null;
  onClose: () => void;
  onChanged?: () => void;
}

export function SessionDetailSheet({ sessionId, onClose, onChanged }: Props) {
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState("preview");
  const [confirmDestroy, setConfirmDestroy] = useState(false);
  const [busy, setBusy] = useState<"destroy" | "submit" | null>(null);

  const idRef = useRef<string | null>(null);

  const load = useCallback(async (id: string) => {
    try {
      const d = await getSession(id);
      // Ignore responses for a session we've since navigated away from.
      if (idRef.current === id) {
        setDetail(d);
        setError(null);
      }
    } catch (err) {
      if (idRef.current === id) setError((err as Error).message);
    }
  }, []);

  useEffect(() => {
    idRef.current = sessionId;
    if (!sessionId) {
      setDetail(null);
      setError(null);
      return;
    }
    setLoading(true);
    setDetail(null);
    setError(null);
    setTab("preview");
    setConfirmDestroy(false);
    setBusy(null);
    load(sessionId).finally(() => {
      if (idRef.current === sessionId) setLoading(false);
    });
  }, [sessionId, load]);

  // Poll every 4s while the session is ACTIVE; stop once it ends.
  const active = detail?.status === "ACTIVE";
  useEffect(() => {
    if (!sessionId || !active) return;
    const h = setInterval(() => load(sessionId), 4000);
    return () => clearInterval(h);
  }, [sessionId, active, load]);

  async function handleDestroy() {
    if (!sessionId) return;
    if (!confirmDestroy) {
      setConfirmDestroy(true);
      return;
    }
    setBusy("destroy");
    try {
      await destroySession(sessionId);
      toast.success("Sandbox destroyed");
      onChanged?.();
      onClose();
    } catch (err) {
      toast.error((err as Error).message);
      setBusy(null);
      setConfirmDestroy(false);
    }
  }

  async function handleSubmit() {
    if (!sessionId || !detail?.session_token) return;
    setBusy("submit");
    try {
      await submitSession(sessionId, detail.session_token);
      toast.success("Scoring started");
      onChanged?.();
      onClose();
    } catch (err) {
      toast.error((err as Error).message);
      setBusy(null);
    }
  }

  const termUrl = detail ? terminalSrc(detail) : undefined;

  return (
    <Sheet open={sessionId != null} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="flex w-full flex-col gap-0 p-0 sm:max-w-3xl">
        <SheetHeader className="border-b">
          {loading || !detail ? (
            <div className="space-y-2">
              <Skeleton className="h-5 w-48" />
              <Skeleton className="h-4 w-64" />
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2">
                <SheetTitle>{detail.candidate_id}</SheetTitle>
                <StatusBadge status={detail.status} />
              </div>
              <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground">
                <span>{shortId(detail.session_id)}</span>
                <span>·</span>
                <span>{detail.question_id}</span>
                <span>·</span>
                <span>expires {relTime(detail.expires_at)}</span>
              </div>
            </>
          )}
        </SheetHeader>

        <div className="flex-1 overflow-y-auto p-4">
          {error && !detail && (
            <div className="rounded-md border border-destructive/40 bg-destructive/10 px-4 py-3 font-mono text-xs text-destructive">
              {error}
            </div>
          )}

          {loading && !detail && (
            <div className="space-y-3">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-[70vh] w-full" />
            </div>
          )}

          {detail && (
            <Tabs value={tab} onValueChange={(v) => setTab(v as string)}>
              <TabsList className="w-full">
                <TabsTrigger value="preview">Preview</TabsTrigger>
                <TabsTrigger value="terminal">Terminal</TabsTrigger>
                <TabsTrigger value="info">Info</TabsTrigger>
              </TabsList>

              <TabsContent value="preview" className="pt-3">
                {detail.status === "ACTIVE" ? (
                  detail.preview_url ? (
                    <iframe
                      src={detail.preview_url}
                      className="h-[70vh] w-full rounded-md border"
                    />
                  ) : (
                    <Empty>
                      This template is a backend API — use the Terminal or hit the app URL.
                      {detail.app_url && (
                        <a
                          href={detail.app_url}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-2 block break-all font-mono text-xs text-primary underline underline-offset-4"
                        >
                          {detail.app_url}
                        </a>
                      )}
                    </Empty>
                  )
                ) : (
                  <Empty>Session ended — no live preview.</Empty>
                )}
              </TabsContent>

              <TabsContent value="terminal" className="pt-3">
                {detail.status === "ACTIVE" && termUrl ? (
                  <iframe
                    src={termUrl}
                    className="h-[70vh] w-full rounded-md border bg-black"
                  />
                ) : (
                  <Empty>Session ended.</Empty>
                )}
              </TabsContent>

              <TabsContent value="info" className="pt-3">
                <dl className="grid gap-3 text-sm">
                  <Row label="Candidate">{detail.candidate_id}</Row>
                  <Row label="Question">
                    <span className="font-mono text-xs">{detail.question_id}</span>
                  </Row>
                  <Row label="Status">
                    <StatusBadge status={detail.status} />
                  </Row>
                  <Row label="Session ID">
                    <span className="font-mono text-xs">{detail.session_id}</span>
                  </Row>
                  <Row label="Expires">{relTime(detail.expires_at)}</Row>
                  <Row label="App URL">
                    {detail.app_url ? (
                      <a
                        href={detail.app_url}
                        target="_blank"
                        rel="noreferrer"
                        className="break-all font-mono text-xs text-primary underline underline-offset-4"
                      >
                        {detail.app_url}
                      </a>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </Row>
                  {detail.session_token && (
                    <div className="grid gap-1.5">
                      <dt className="text-xs text-muted-foreground">Session token</dt>
                      <dd className="overflow-x-auto rounded-md border bg-muted/50 p-2 font-mono text-[11px] break-all">
                        {detail.session_token}
                      </dd>
                    </div>
                  )}
                </dl>
              </TabsContent>
            </Tabs>
          )}
        </div>

        {detail?.status === "ACTIVE" && (
          <div className="flex items-center justify-end gap-2 border-t p-4">
            {detail.session_token && (
              <Button
                variant="outline"
                className="mr-auto"
                onClick={() =>
                  window.open(
                    playgroundHref(detail.session_id, detail.session_token!),
                    "_blank",
                    "noreferrer",
                  )
                }
              >
                <Code2 className="mr-2 h-4 w-4" />
                Open playground
              </Button>
            )}
            <Button
              variant="destructive"
              onClick={handleDestroy}
              disabled={busy !== null}
            >
              {busy === "destroy"
                ? "Destroying…"
                : confirmDestroy
                  ? "Click to confirm"
                  : "Destroy"}
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={busy !== null || !detail.session_token}
            >
              {busy === "submit" ? "Submitting…" : "Submit & score"}
            </Button>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-[70vh] w-full flex-col items-center justify-center rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
      <div className="max-w-sm">{children}</div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <dt className="shrink-0 text-xs text-muted-foreground">{label}</dt>
      <dd className="text-right">{children}</dd>
    </div>
  );
}
