/** Small presentational building blocks shared by every page. No data fetching here. */
import type {ReactNode} from "react";

export const Card = ({title, sub, right, children, className = ""}: {title?: ReactNode; sub?: ReactNode; right?: ReactNode; children: ReactNode; className?: string}) => (
  <section className={`card ${className}`}>
    {(title || right) && <div className="card-head"><div><h3>{title}</h3>{sub && <p className="muted">{sub}</p>}</div>{right}</div>}
    {children}
  </section>
);

export const Pill = ({tone = "neutral", children}: {tone?: "ok" | "warn" | "bad" | "neutral" | "info"; children: ReactNode}) => <span className={`pill ${tone}`}>{children}</span>;

export const Stat = ({k, v, sub, tone}: {k: ReactNode; v: ReactNode; sub?: ReactNode; tone?: "ok" | "warn" | "bad"}) => (
  <div className={`stat ${tone ?? ""}`}><div className="stat-v">{v}</div><div className="stat-k">{k}</div>{sub && <div className="stat-sub">{sub}</div>}</div>
);

export const Button = ({children, kind = "primary", ...rest}: {children: ReactNode; kind?: "primary" | "ghost" | "danger"} & React.ButtonHTMLAttributes<HTMLButtonElement>) => (
  <button className={`btn ${kind}`} {...rest}>{children}</button>
);

export const Field = ({label, children}: {label: ReactNode; children: ReactNode}) => <label className="field"><span>{label}</span>{children}</label>;

export const Loading = ({what = "loading"}: {what?: string}) => <div className="muted loading">{what}…</div>;

export const ErrorNote = ({error}: {error: unknown}) => <div className="note bad">✕ {error instanceof Error ? error.message : String(error)}</div>;

export const Provenance = ({children}: {children: ReactNode}) => <p className="provenance">{children}</p>;

export const Table = ({head, rows}: {head: ReactNode[]; rows: ReactNode[][]}) => (
  <div className="tablewrap"><table><thead><tr>{head.map((h, i) => <th key={i}>{h}</th>)}</tr></thead><tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}>{c}</td>)}</tr>)}</tbody></table></div>
);
