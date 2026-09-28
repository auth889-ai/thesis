import {Pill} from "@/components/ui";

const TYPE: Record<string, string> = {paper: "paper", dataset: "dataset", standard: "standard", software: "software", api: "service", report: "report", book: "book"};

/** One reference: title, authors and venue, identifiers, what it is used for, and the code files that use it. */
export function ReferenceItem({it}: {it: any}) {
  const ids = [
    it.doi && <a key="doi" href={`https://doi.org/${it.doi}`} target="_blank" rel="noopener">doi:{it.doi}</a>,
    it.data_doi && <a key="ddoi" href={`https://doi.org/${it.data_doi}`} target="_blank" rel="noopener">data doi:{it.data_doi}</a>,
    it.url && !it.doi && <a key="url" href={it.url} target="_blank" rel="noopener">{String(it.url).replace(/^https?:\/\//, "")}</a>,
  ].filter(Boolean);
  return (
    <li className={`rf-item ${it.context_only ? "ctx" : ""}`}>
      <div className="rf-title"><span className="rf-type">{TYPE[it.type] ?? it.type}</span> {it.title}</div>
      <div className="muted small">{it.authors ?? ""}{it.venue && <> · <i>{it.venue}</i></>}{it.year && <> · {it.year}</>}{ids.length > 0 && <> · {ids.map((x, i) => <span key={i}>{i > 0 && " · "}{x}</span>)}</>}</div>
      <div className="small"><b>Used for:</b> {it.used_for}{it.context_only && <> <Pill tone="warn">context only</Pill></>}</div>
      {it.code && <div className="small"><b>Code:</b> {it.code}</div>}
      {it.files?.length > 0 && <div className="rf-files">{it.files.map((f: string) => <code key={f}>{f}</code>)}</div>}
    </li>
  );
}
