/** Horizontal tabs. The parent owns the selected key so a tab can be opened from elsewhere on the page. */
export function Tabs<K extends string>({items, value, onChange}: {items: {key: K; label: string}[]; value: K; onChange: (k: K) => void}) {
  return <div className="tabs" role="tablist">{items.map((t) => <button key={t.key} role="tab" aria-selected={t.key === value} className={t.key === value ? "on" : ""} onClick={() => onChange(t.key)}>{t.label}</button>)}</div>;
}

export function Segmented<K extends string>({items, value, onChange}: {items: {key: K; label: string}[]; value: K; onChange: (k: K) => void}) {
  return <div className="seg">{items.map((t) => <button key={t.key} className={t.key === value ? "on" : ""} onClick={() => onChange(t.key)}>{t.label}</button>)}</div>;
}
