"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import { toast } from "sonner";
import {
  getPlayInfo,
  getResult,
  listFiles,
  readFile,
  writeFile,
  submitSession,
  PlayInfo,
  PlayResult,
} from "@/lib/api";
import { apiBase } from "@/lib/api";
import { Button } from "@/components/ui/button";

// Playground is the candidate IDE: Monaco editing the LIVE sandbox files, a live
// preview (frontend templates hot-reload on save), an embedded terminal, and
// submit→score. Everything is authorized by the per-session token.
export function Playground({ session, token }: { session: string; token: string }) {
  const [info, setInfo] = useState<PlayInfo | null>(null);
  const [files, setFiles] = useState<string[]>([]);
  const [activePath, setActivePath] = useState<string>("");
  const [content, setContent] = useState<string>("");
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<PlayResult | null>(null);
  const [tab, setTab] = useState<"preview" | "terminal">("preview");
  const [err, setErr] = useState<string>("");
  const contentRef = useRef(content);
  contentRef.current = content;
  const activeRef = useRef(activePath);
  activeRef.current = activePath;
  const previewRef = useRef<HTMLIFrameElement>(null);

  const openFile = useCallback(
    async (path: string) => {
      try {
        const text = await readFile(session, token, path);
        setActivePath(path);
        setContent(text);
        setDirty(false);
      } catch (e) {
        toast.error((e as Error).message);
      }
    },
    [session, token],
  );

  // Bootstrap: play info + file list, open the most likely starter file.
  useEffect(() => {
    (async () => {
      try {
        const [pi, fs] = await Promise.all([getPlayInfo(session, token), listFiles(session, token)]);
        setInfo(pi);
        setFiles(fs);
        if (pi.kind !== "frontend") setTab("terminal");
        const first =
          fs.find((f) => /App\.(tsx|jsx)$/.test(f)) ?? fs.find((f) => /\.(tsx|jsx|ts|js|py)$/.test(f)) ?? fs[0];
        if (first) await openFile(first);
      } catch (e) {
        setErr((e as Error).message);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, token]);

  const save = useCallback(async () => {
    const path = activeRef.current;
    if (!path || saving) return;
    setSaving(true);
    try {
      await writeFile(session, token, path, contentRef.current);
      setDirty(false);
      toast.success(`Saved ${path}`);
      // Nudge the preview to reflect the change (Vite HMR usually does this itself).
      if (info?.kind === "frontend" && previewRef.current) {
        const f = previewRef.current;
        // soft refresh
        f.src = f.src;
      }
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  }, [session, token, saving, info]);

  // Cmd/Ctrl+S saves.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        void save();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [save]);

  async function submit() {
    if (submitting) return;
    if (dirty) await save();
    setSubmitting(true);
    setResult({ submitted: true, status: "scoring" });
    try {
      await submitSession(session, token);
      // Poll for the async score.
      for (let i = 0; i < 60; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        const res = await getResult(session, token);
        setResult(res);
        if (res.submitted && res.status && res.status !== "scoring") break;
      }
    } catch (e) {
      toast.error((e as Error).message);
      setResult(null);
    } finally {
      setSubmitting(false);
    }
  }

  if (err) {
    return (
      <div className="grid h-screen place-items-center bg-[#1e1e1e] text-rose-400">
        <div className="font-mono text-sm">playground unavailable — {err}</div>
      </div>
    );
  }

  const submitted = result?.submitted && result.status && result.status !== "scoring";
  const previewUrl = info?.preview_url;
  const terminalUrl = info?.terminal_page ? apiBase() + info.terminal_page : undefined;

  return (
    <div className="flex h-screen flex-col bg-[#1e1e1e] text-[#ddd]">
      {/* top bar */}
      <header className="flex h-12 shrink-0 items-center gap-3 border-b border-[#333] px-4">
        <span className="font-semibold">{info?.title ?? "Playground"}</span>
        <span className="font-mono text-[11px] text-[#888]">
          {info?.candidate_id} · {info?.question_id}
        </span>
        <div className="ml-auto flex items-center gap-2">
          {result &&
            (result.status === "scoring" ? (
              <Badge tone="amber">scoring…</Badge>
            ) : submitted ? (
              <Badge tone="emerald">
                score {result.score}/{result.max_score}
              </Badge>
            ) : null)}
          <Button size="sm" variant="outline" onClick={save} disabled={!dirty || saving}>
            {saving ? "Saving…" : dirty ? "Save  ⌘S" : "Saved"}
          </Button>
          <Button size="sm" onClick={submit} disabled={submitting}>
            {submitting ? "Submitting…" : "Submit & score"}
          </Button>
        </div>
      </header>

      {/* body: files | editor | preview/terminal */}
      <div className="flex min-h-0 flex-1">
        {/* file tree */}
        <aside className="w-52 shrink-0 overflow-auto border-r border-[#333] bg-[#181818] py-2">
          <div className="px-3 pb-1 text-[10px] uppercase tracking-wider text-[#777]">Files</div>
          {files.map((f) => (
            <button
              key={f}
              onClick={() => openFile(f)}
              className={`block w-full truncate px-3 py-1 text-left font-mono text-[12px] hover:bg-[#2a2a2a] ${
                f === activePath ? "bg-[#2d2d2d] text-white" : "text-[#bbb]"
              }`}
            >
              {f}
              {f === activePath && dirty ? " ●" : ""}
            </button>
          ))}
        </aside>

        {/* editor */}
        <div className="min-w-0 flex-1">
          <Editor
            height="100%"
            theme="vs-dark"
            path={activePath}
            language={langFor(activePath)}
            value={content}
            onChange={(v) => {
              setContent(v ?? "");
              setDirty(true);
            }}
            options={{
              fontSize: 13,
              minimap: { enabled: false },
              scrollBeyondLastLine: false,
              automaticLayout: true,
              tabSize: 2,
            }}
          />
        </div>

        {/* preview / terminal */}
        <div className="flex w-[42%] shrink-0 flex-col border-l border-[#333]">
          <div className="flex h-9 shrink-0 items-center gap-1 border-b border-[#333] bg-[#181818] px-2">
            {info?.kind === "frontend" && (
              <TabButton active={tab === "preview"} onClick={() => setTab("preview")}>
                Preview
              </TabButton>
            )}
            <TabButton active={tab === "terminal"} onClick={() => setTab("terminal")}>
              Terminal
            </TabButton>
            {tab === "preview" && previewUrl && (
              <a
                href={previewUrl}
                target="_blank"
                rel="noreferrer"
                className="ml-auto font-mono text-[11px] text-sky-400 hover:underline"
              >
                open ↗
              </a>
            )}
          </div>
          <div className="min-h-0 flex-1 bg-white">
            {tab === "preview" && previewUrl ? (
              <iframe ref={previewRef} src={previewUrl} className="h-full w-full border-0" title="preview" />
            ) : terminalUrl ? (
              <iframe src={terminalUrl} className="h-full w-full border-0" title="terminal" />
            ) : (
              <div className="grid h-full place-items-center bg-[#1e1e1e] text-sm text-[#888]">no view</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded px-2.5 py-1 text-xs ${active ? "bg-[#2d2d2d] text-white" : "text-[#aaa] hover:bg-[#252525]"}`}
    >
      {children}
    </button>
  );
}

function Badge({ tone, children }: { tone: "amber" | "emerald"; children: React.ReactNode }) {
  const cls =
    tone === "emerald"
      ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-400"
      : "border-amber-500/40 bg-amber-500/15 text-amber-400";
  return (
    <span className={`rounded-md border px-2 py-0.5 font-mono text-[11px] ${cls}`}>{children}</span>
  );
}

function langFor(path: string): string {
  if (/\.(tsx|ts)$/.test(path)) return "typescript";
  if (/\.(jsx|js|cjs|mjs)$/.test(path)) return "javascript";
  if (/\.py$/.test(path)) return "python";
  if (/\.css$/.test(path)) return "css";
  if (/\.html?$/.test(path)) return "html";
  if (/\.json$/.test(path)) return "json";
  if (/\.md$/.test(path)) return "markdown";
  return "plaintext";
}
