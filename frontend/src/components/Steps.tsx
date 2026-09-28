/** A row of pipeline stages: done, live, pending, or failed. Used by every long-running job. */
export function Steps({steps, current, error, done = false}: {steps: string[]; current: number; error?: string | null; done?: boolean}) {
  return (
    <div className="steps">
      {steps.map((s, i) => { const state = done || i < current ? "done" : i === current && !error ? "live" : ""; return <span key={s} className={state}>{state === "done" ? "✓" : state === "live" ? "●" : "○"} {s}</span>; })}
      {error && <span className="bad">✕ {error}</span>}
    </div>
  );
}
