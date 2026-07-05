"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { apiKey, setApiKey } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

// SettingsCard lets an operator paste their org API key (hyk_…). The control plane
// requires it on /v1/* when auth is enabled; it is stored in localStorage and sent
// as a Bearer header by the API client. Never logged or shown back in full.
export function SettingsCard() {
  const [key, setKey] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setSaved(apiKey() !== "");
  }, []);

  function save() {
    setApiKey(key);
    setSaved(true);
    setKey("");
    toast.success("API key saved — reads and writes now carry it");
  }

  function clear() {
    setApiKey("");
    setSaved(false);
    toast.message("API key cleared");
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Orchestrator</CardTitle>
        <CardDescription>Connection and operator credential used by this dashboard.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-1.5">
          <Label htmlFor="api-key">Operator API key</Label>
          <div className="flex gap-2">
            <Input
              id="api-key"
              type="password"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder={saved ? "•••••••••• (a key is set)" : "hyk_…"}
              className="font-mono"
            />
            <Button onClick={save} disabled={key.trim() === ""}>
              Save
            </Button>
            {saved && (
              <Button variant="outline" onClick={clear}>
                Clear
              </Button>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            Required on <code className="font-mono">/v1/*</code> when auth is enabled. Also settable via the{" "}
            <code className="font-mono">?key=</code> query param or{" "}
            <code className="font-mono">NEXT_PUBLIC_API_KEY</code>. Stored locally in this browser only.
          </p>
        </div>

        <p className="text-sm text-muted-foreground">
          Set the API base via the field in the header, the <code className="font-mono">?api=</code> query
          param, or <code className="font-mono">NEXT_PUBLIC_API_BASE</code>. The dashboard polls{" "}
          <code className="font-mono">/v1/sessions</code> and <code className="font-mono">/v1/templates</code>{" "}
          every 3s.
        </p>
      </CardContent>
    </Card>
  );
}
