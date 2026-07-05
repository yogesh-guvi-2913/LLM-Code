"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { scaleTemplate, Template } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

// ScaleCell is the per-template warm-depth control — the same knob scheduled scaling
// drives (POST /v1/templates/:id/min_warm). Raise it before a window, lower it after.
export function ScaleCell({ template }: { template: Template }) {
  const [value, setValue] = useState(String(template.min_warm));
  const [saving, setSaving] = useState(false);

  // Track the server value when the poll updates, unless the user is mid-edit.
  const [dirty, setDirty] = useState(false);
  useEffect(() => {
    if (!dirty) setValue(String(template.min_warm));
  }, [template.min_warm, dirty]);

  const n = Number(value);
  const invalid = !Number.isInteger(n) || n < 0 || n > 200;
  const changed = n !== template.min_warm;

  async function save() {
    if (invalid || saving) return;
    setSaving(true);
    try {
      await scaleTemplate(template.id, n);
      toast.success(`${template.id} warm depth → ${n}`);
      setDirty(false);
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex items-center gap-1.5">
      <Input
        type="number"
        min={0}
        max={200}
        value={value}
        onChange={(e) => {
          setDirty(true);
          setValue(e.target.value);
        }}
        aria-invalid={invalid}
        className="h-8 w-16 font-mono text-xs"
      />
      <Button size="sm" variant="outline" disabled={invalid || !changed || saving} onClick={save}>
        {saving ? "…" : "Set"}
      </Button>
    </div>
  );
}
