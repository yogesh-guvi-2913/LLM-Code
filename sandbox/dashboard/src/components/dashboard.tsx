"use client";

import { useEffect, useRef, useState } from "react";
import { Activity, Boxes, CalendarDays, Download, Layers, LayoutGrid, Plus } from "lucide-react";
import { getSessions, getTemplates } from "@/lib/api";
import { usePoll } from "@/lib/use-poll";
import { clockTime } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar, Section } from "./app-sidebar";
import { Search } from "./search";
import { ThemeToggle } from "./theme-toggle";
import { Overview, Bucket } from "./overview";
import { RecentSessions } from "./recent-sessions";
import { SessionsTable } from "./sessions-table";
import { TemplatesTable } from "./templates-table";
import { CreateSandboxDialog } from "./create-sandbox-dialog";
import { CreateTemplateDialog } from "./create-template-dialog";
import { SessionDetailSheet } from "./session-detail-sheet";
import { SettingsCard } from "./settings-card";
import { ApiKeysCard } from "./api-keys-card";
import { CostPanel } from "./cost-panel";
import { FleetTable } from "./fleet-table";
import { Architecture } from "./architecture";
import { Schedule } from "./schedule";

const MAX_BUCKETS = 24;

const TITLES: Record<Section, string> = {
  overview: "Overview",
  sessions: "Sessions",
  templates: "Templates",
  schedule: "Schedule",
  fleet: "Fleet",
  architecture: "How it works",
  settings: "Settings",
};

export function Dashboard() {
  const sessions = usePoll(getSessions, 3000);
  const templates = usePoll(getTemplates, 3000);
  const [series, setSeries] = useState<Bucket[]>([]);
  const [active, setActive] = useState<Section>("overview");
  const [sandboxOpen, setSandboxOpen] = useState(false);
  const [templateOpen, setTemplateOpen] = useState(false);
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const lastStamp = useRef<number | null>(null);

  const rows = sessions.data ?? [];
  const tmpls = templates.data ?? [];
  const activeCount = rows.filter((s) => s.status === "ACTIVE").length;
  const warm = tmpls.reduce((n, t) => n + t.warm, 0);
  const scored = rows.filter((s) => s.score != null).length;
  const langs = Array.from(new Set(tmpls.map((t) => t.language))).join(", ");

  useEffect(() => {
    const stamp = Math.max(sessions.lastUpdated ?? 0, templates.lastUpdated ?? 0);
    if (!stamp || stamp === lastStamp.current) return;
    if (sessions.lastUpdated == null || templates.lastUpdated == null) return;
    lastStamp.current = stamp;
    setSeries((prev) => [...prev, { name: clockTime(), total: activeCount }].slice(-MAX_BUCKETS));
  }, [sessions.lastUpdated, templates.lastUpdated, activeCount]);

  const unreachable = sessions.error || templates.error;

  return (
    <SidebarProvider>
      <AppSidebar
        active={active}
        onSelect={setActive}
        counts={{ sessions: rows.length, templates: tmpls.length }}
      />
      <SidebarInset>
        <header className="flex h-16 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mr-2 h-4" />
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">{TITLES[active]}</span>
            <span className="inline-flex items-center gap-1.5 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 font-mono text-[11px] font-medium text-emerald-500">
              <span className="live-dot h-1.5 w-1.5 rounded-full bg-emerald-500" />
              {unreachable ? "OFFLINE" : "LIVE"}
            </span>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <Search />
            <ThemeToggle />
          </div>
        </header>

        <div className="flex-1 space-y-4 p-8 pt-6">
          {unreachable && (
            <div className="rounded-md border border-destructive/40 bg-destructive/10 px-4 py-3 font-mono text-xs text-destructive">
              orchestrator unreachable — {unreachable}
            </div>
          )}

          <div className="flex items-center justify-between space-y-2">
            <h2 className="text-3xl font-bold tracking-tight">{TITLES[active]}</h2>
            <div className="flex items-center space-x-2">
              <Button variant="outline" size="sm">
                <CalendarDays className="mr-2 h-4 w-4" />
                Last 30 minutes
              </Button>
              <Button variant="outline" size="sm" onClick={() => exportJSON(rows)}>
                <Download className="mr-2 h-4 w-4" />
                Export
              </Button>
              <Button size="sm" onClick={() => setSandboxOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                New sandbox
              </Button>
            </div>
          </div>

          {active === "overview" && (
            <div className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <Metric title="Concurrent sandboxes" value={activeCount} sub="Live limit: 20" icon={<Boxes className="h-4 w-4 text-muted-foreground" />} />
                <Metric title="Warm containers" value={warm} sub="Ready to claim instantly" icon={<Layers className="h-4 w-4 text-muted-foreground" />} />
                <Metric title="Templates" value={tmpls.length} sub={langs || "—"} icon={<LayoutGrid className="h-4 w-4 text-muted-foreground" />} />
                <Metric title="Total sessions" value={rows.length} sub={`${scored} scored`} icon={<Activity className="h-4 w-4 text-muted-foreground" />} />
              </div>

              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
                <Card className="lg:col-span-4">
                  <CardHeader>
                    <CardTitle>Overview</CardTitle>
                    <CardDescription>Concurrent sandboxes, sampled live every 3s.</CardDescription>
                  </CardHeader>
                  <CardContent className="pl-2">
                    <Overview data={series} />
                  </CardContent>
                </Card>
                <Card className="lg:col-span-3">
                  <CardHeader>
                    <CardTitle>Recent sessions</CardTitle>
                    <CardDescription>{rows.length} sessions total.</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <RecentSessions rows={rows} onSelect={setSelectedSession} />
                  </CardContent>
                </Card>
              </div>

              <CostPanel />
            </div>
          )}

          {active === "sessions" && (
            <SessionsTable rows={rows} onSelect={setSelectedSession} />
          )}

          {active === "templates" && (
            <div className="space-y-4">
              <div className="flex justify-end">
                <Button size="sm" onClick={() => setTemplateOpen(true)}>
                  <Plus className="mr-2 h-4 w-4" />
                  New template
                </Button>
              </div>
              <TemplatesTable rows={tmpls} />
            </div>
          )}

          {active === "schedule" && <Schedule />}

          {active === "fleet" && <FleetTable />}

          {active === "architecture" && <Architecture />}

          {active === "settings" && (
            <div className="space-y-4">
              <SettingsCard />
              <ApiKeysCard />
            </div>
          )}
        </div>
      </SidebarInset>

      <CreateSandboxDialog
        open={sandboxOpen}
        onOpenChange={setSandboxOpen}
        templates={tmpls}
        onCreated={(id) => setSelectedSession(id)}
      />
      <CreateTemplateDialog
        open={templateOpen}
        onOpenChange={setTemplateOpen}
        onCreated={() => {}}
      />
      <SessionDetailSheet
        sessionId={selectedSession}
        onClose={() => setSelectedSession(null)}
      />
    </SidebarProvider>
  );
}

function Metric({
  title,
  value,
  sub,
  icon,
}: {
  title: string;
  value: number;
  sub: string;
  icon: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        <p className="text-xs text-muted-foreground">{sub}</p>
      </CardContent>
    </Card>
  );
}

function exportJSON(rows: unknown) {
  const blob = new Blob([JSON.stringify(rows, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "flash-sessions.json";
  a.click();
  URL.revokeObjectURL(url);
}
