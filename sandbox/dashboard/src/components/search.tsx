"use client";

import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { apiBase, setApiBase } from "@/lib/api";

// Doubles as the "Search" slot in the shadcn header — here it sets the
// orchestrator API base the dashboard polls.
export function Search() {
  const [api, setApi] = useState("");
  useEffect(() => setApi(apiBase()), []);

  function commit(v: string) {
    setApi(v);
    setApiBase(v);
    window.location.reload();
  }

  return (
    <Input
      value={api}
      spellCheck={false}
      onChange={(e) => setApi(e.target.value)}
      onBlur={(e) => commit(e.target.value)}
      onKeyDown={(e) => e.key === "Enter" && commit((e.target as HTMLInputElement).value)}
      placeholder="API base…"
      className="h-9 font-mono text-xs md:w-[210px] lg:w-[260px]"
    />
  );
}
