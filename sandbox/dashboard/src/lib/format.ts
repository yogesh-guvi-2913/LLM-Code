export function relTime(ts?: string): string {
  if (!ts) return "—";
  const d = (Date.now() - new Date(ts).getTime()) / 1000;
  const a = Math.abs(d);
  const sign = d < 0 ? "in " : "";
  const suf = d < 0 ? "" : " ago";
  if (a < 60) return `${sign}${Math.round(a)}s${suf}`;
  if (a < 3600) return `${sign}${Math.round(a / 60)}m${suf}`;
  if (a < 86400) return `${sign}${Math.round(a / 3600)}h${suf}`;
  return `${sign}${Math.round(a / 86400)}d${suf}`;
}

export function shortId(id: string): string {
  return id.replace(/^[a-z]+_/, "").slice(0, 12);
}

export function clockTime(d = new Date()): string {
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
