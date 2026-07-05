"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { createTemplate, TemplateKind } from "@/lib/api";
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
  onCreated: () => void;
}

const ID_RE = /^[a-z0-9][a-z0-9-]{0,31}$/;

export function CreateTemplateDialog({ open, onOpenChange, onCreated }: Props) {
  const [id, setId] = useState("");
  const [title, setTitle] = useState("");
  const [language, setLanguage] = useState("");
  const [kind, setKind] = useState<TemplateKind>("api");
  const [image, setImage] = useState("");
  const [devCmd, setDevCmd] = useState("");
  const [minWarm, setMinWarm] = useState("1");
  const [vcpu, setVcpu] = useState("0.5");
  const [memoryMb, setMemoryMb] = useState("512");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setId("");
      setTitle("");
      setLanguage("");
      setKind("api");
      setImage("");
      setDevCmd("");
      setMinWarm("1");
      setVcpu("0.5");
      setMemoryMb("512");
      setSubmitting(false);
    }
  }, [open]);

  const idValid = ID_RE.test(id);
  const warmNum = Number(minWarm);
  const warmValid = Number.isFinite(warmNum) && warmNum >= 0 && warmNum <= 10;
  const valid =
    idValid && image.trim() !== "" && devCmd.trim() !== "" && warmValid;

  async function handleSubmit() {
    if (!valid || submitting) return;
    setSubmitting(true);
    try {
      await createTemplate({
        id: id.trim(),
        title: title.trim() || undefined,
        language: language.trim() || undefined,
        kind,
        image: image.trim(),
        dev_cmd: devCmd.trim(),
        min_warm: warmNum,
        vcpu: Number(vcpu),
        memory_mb: Number(memoryMb),
      });
      toast.success(`Template "${id.trim()}" created`);
      onOpenChange(false);
      onCreated();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Create template</DialogTitle>
          <DialogDescription>
            Define a warm-pool snapshot from a Docker image. Containers are pre-booted so sandboxes
            claim instantly.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-1">
          <div className="grid gap-1.5">
            <Label htmlFor="tpl-id">ID</Label>
            <Input
              id="tpl-id"
              value={id}
              onChange={(e) => setId(e.target.value)}
              placeholder="q1-express-api"
              aria-invalid={id !== "" && !idValid}
            />
            <p className="text-xs text-muted-foreground">
              Lowercase letters, digits, dashes — used in URLs/labels.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <Label htmlFor="tpl-title">Title</Label>
              <Input
                id="tpl-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Express API"
              />
              <p className="text-xs text-muted-foreground">Optional display name.</p>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="tpl-language">Language</Label>
              <Input
                id="tpl-language"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                placeholder="Node.js"
              />
              <p className="text-xs text-muted-foreground">Optional, shown as a badge.</p>
            </div>
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="tpl-kind">Kind</Label>
            <Select value={kind} onValueChange={(v) => setKind(v as TemplateKind)}>
              <SelectTrigger id="tpl-kind" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="api">api</SelectItem>
                <SelectItem value="frontend">frontend</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Frontend templates get a browser preview; API templates expose the app URL.
            </p>
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="tpl-image">Image</Label>
            <Input
              id="tpl-image"
              value={image}
              onChange={(e) => setImage(e.target.value)}
              placeholder="flash-sandbox:q1-express-api-v1"
              className="font-mono"
            />
            <p className="text-xs text-muted-foreground">
              Must exist in the Docker daemon, e.g. flash-sandbox:q1-express-api-v1.
            </p>
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="tpl-devcmd">Entrypoint (dev_cmd)</Label>
            <Input
              id="tpl-devcmd"
              value={devCmd}
              onChange={(e) => setDevCmd(e.target.value)}
              placeholder="npx vite --host 0.0.0.0 --port 3000"
              className="font-mono"
            />
            <p className="text-xs text-muted-foreground">
              Command that starts the dev server on port 3000, e.g. &apos;node server.js&apos;.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <div className="grid gap-1.5">
              <Label htmlFor="tpl-warm">Min warm</Label>
              <Input
                id="tpl-warm"
                type="number"
                min={0}
                max={10}
                value={minWarm}
                onChange={(e) => setMinWarm(e.target.value)}
                aria-invalid={!warmValid}
              />
              <p className="text-xs text-muted-foreground">0–10</p>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="tpl-vcpu">vCPU</Label>
              <Input
                id="tpl-vcpu"
                type="number"
                step="0.1"
                min={0.1}
                value={vcpu}
                onChange={(e) => setVcpu(e.target.value)}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="tpl-mem">Memory (MB)</Label>
              <Input
                id="tpl-mem"
                type="number"
                min={64}
                value={memoryMb}
                onChange={(e) => setMemoryMb(e.target.value)}
              />
            </div>
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
