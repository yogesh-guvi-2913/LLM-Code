"use client";

import { useEffect, useState } from "react";
import { Playground } from "@/components/playground";

// /play?session=<id>&token=<token> — the candidate IDE. Reads its credentials from
// the URL (exactly how an assessment platform embeds it), so it needs no operator
// key. Params are read client-side to avoid SSR/suspense coupling.
export default function PlayPage() {
  const [params, setParams] = useState<{ session: string; token: string } | null>(null);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    setParams({ session: q.get("session") ?? "", token: q.get("token") ?? "" });
  }, []);

  if (!params) {
    return <div className="grid h-screen place-items-center bg-[#1e1e1e] text-sm text-[#888]">loading…</div>;
  }
  if (!params.session || !params.token) {
    return (
      <div className="grid h-screen place-items-center bg-[#1e1e1e] text-sm text-rose-400">
        missing ?session= and ?token=
      </div>
    );
  }
  return <Playground session={params.session} token={params.token} />;
}
