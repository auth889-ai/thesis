import type {ReactNode} from "react";

/** The assistant writes short markdown (bold, bullets, line breaks). Render just that: no HTML injection, no library. */
export function Prose({text}: {text: string}) {
  const lines = text.replace(/\s*✓\s*/g, "\n• ").split(/\n+/).map((l) => l.trim()).filter(Boolean);
  return <div className="prose">{lines.map((l, i) => <p key={i} className={/^[•\-*]\s/.test(l) ? "bullet" : ""}>{inline(l.replace(/^[•\-*]\s+/, ""))}</p>)}</div>;
}

function inline(s: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /\*\*(.+?)\*\*/g;
  let last = 0, m: RegExpExecArray | null, k = 0;
  while ((m = re.exec(s))) {
    if (m.index > last) out.push(s.slice(last, m.index));
    out.push(<b key={k++}>{m[1]}</b>);
    last = m.index + m[0].length;
  }
  if (last < s.length) out.push(s.slice(last));
  return out;
}
