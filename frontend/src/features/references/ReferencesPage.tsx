import {useQuery} from "@tanstack/react-query";

import {Loading, Pill} from "@/components/ui";
import {api} from "@/lib/api";
import {ReferenceItem} from "./ReferenceItem";
import "./references.css";

/** REFERENCES: every paper, dataset, standard, tool and service the code uses, with the files that use it. Read from docs/references.json. */
export function ReferencesPage() {
  const R = useQuery({queryKey: ["references"], queryFn: () => api.references()});
  if (R.isError) return <div className="note bad">References unavailable: {(R.error as Error).message}</div>;
  if (!R.data) return <Loading what="loading the references" />;
  const groups: {id: string; title: string; items: any[]}[] = R.data.groups;
  return (
    <div className="stack">
      <div className="card">
        <p style={{margin: 0}}>{R.data.count} references, grouped by the three contributions of the project. Each entry names the files that use it, so every citation is traceable to code. Source: <code>{R.data.source}</code>; the same list is exported as <code>docs/REFERENCES.md</code>.</p>
        <nav className="row rf-toc">{groups.map((g) => <a key={g.id} href={`#rf-${g.id}`} onClick={(e) => { e.preventDefault(); document.getElementById(`rf-${g.id}`)?.scrollIntoView({behavior: "smooth", block: "start"}); }}>{g.title} <Pill>{g.items.length}</Pill></a>)}</nav>
      </div>
      {groups.map((g) => (
        <section key={g.id} id={`rf-${g.id}`} className="card">
          <h3>{g.title}</h3>
          <ol className="rf-list">{g.items.map((it, i) => <ReferenceItem key={it.id ?? i} it={it} />)}</ol>
        </section>
      ))}
    </div>
  );
}
