"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, Copy, KeyRound, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import {
  ApiKeyRow,
  createApiKey,
  listApiKeys,
  revokeApiKey,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

// ApiKeysCard is the credential-lifecycle UI: mint named org keys (the raw key
// is shown exactly once — only its hash is stored server-side), see when each
// was last used, and revoke.
export function ApiKeysCard() {
  const [keys, setKeys] = useState<ApiKeyRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [minted, setMinted] = useState<{ name: string; key: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setKeys(await listApiKeys());
      setError(null);
    } catch (e) {
      setError(String((e as Error).message || e));
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function mint() {
    setBusy(true);
    try {
      const created = await createApiKey(name.trim());
      setMinted({ name: created.name, key: created.key });
      setCopied(false);
      setName("");
      toast.success(`Key "${created.name}" created — copy it now, it won't be shown again`);
      refresh();
    } catch (e) {
      toast.error(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  async function revoke(k: ApiKeyRow) {
    try {
      await revokeApiKey(k.id);
      toast.success(`Key "${k.name || k.prefix}" revoked`);
      refresh();
    } catch (e) {
      toast.error(String((e as Error).message || e));
    }
  }

  async function copyMinted() {
    if (!minted) return;
    await navigator.clipboard.writeText(minted.key);
    setCopied(true);
    toast.message("Key copied to clipboard");
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <KeyRound className="h-4 w-4" />
          API keys
        </CardTitle>
        <CardDescription>
          Org credentials for the SDK and API. The raw key is shown once at creation; only a
          hash is stored.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Key name (e.g. ci, backend-prod)"
            className="max-w-xs"
            onKeyDown={(e) => {
              if (e.key === "Enter" && name.trim()) mint();
            }}
          />
          <Button onClick={mint} disabled={busy || name.trim() === ""}>
            <Plus className="mr-2 h-4 w-4" />
            Create key
          </Button>
        </div>

        {minted && (
          <div className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3">
            <p className="mb-2 text-xs font-medium text-amber-600 dark:text-amber-400">
              Key “{minted.name}” — copy it now, it will not be shown again.
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 overflow-x-auto rounded bg-background px-2 py-1.5 font-mono text-xs">
                {minted.key}
              </code>
              <Button size="sm" variant="outline" onClick={copyMinted}>
                {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setMinted(null)}>
                Done
              </Button>
            </div>
          </div>
        )}

        {error && (
          <p className="font-mono text-xs text-destructive">could not load keys — {error}</p>
        )}

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Key</TableHead>
              <TableHead>Created</TableHead>
              <TableHead>Last used</TableHead>
              <TableHead className="w-10" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {(keys ?? []).map((k) => (
              <TableRow key={k.id}>
                <TableCell className="font-medium">{k.name || "—"}</TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {k.prefix}…
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {new Date(k.created_at).toLocaleString()}
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {k.last_used_at ? new Date(k.last_used_at).toLocaleString() : "never"}
                </TableCell>
                <TableCell>
                  <Button
                    size="icon"
                    variant="ghost"
                    className="h-7 w-7 text-muted-foreground hover:text-destructive"
                    title="Revoke key"
                    onClick={() => revoke(k)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {keys !== null && keys.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-sm text-muted-foreground">
                  No keys yet — create one above.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
