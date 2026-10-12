import type {ReactNode} from "react";
import {Link} from "react-router-dom";

import {useT} from "@/i18n";
import {Pill} from "./ui";

export type PlainKind = "simulated" | "real" | "forecast" | "map";
const TONE: Record<PlainKind, "info" | "ok" | "warn" | "neutral"> = {simulated: "info", real: "ok", forecast: "warn", map: "neutral"};

/**
 * A result on an everyday page (CLAUDE.md, plain language rule): one sentence a non-expert understands, a small tag
 * saying whether it is a simulation, a real recording or a forecast, and "How we know →" to the Research page that
 * holds the full table. The sentence's numbers come from the same result file as that table.
 */
export function PlainResult({kind, to, children}: {kind: PlainKind; to: string; children: ReactNode}) {
  const t = useT();
  return (
    <p className="plain-result">
      <span className="plain-sentence">{children}</span>
      <Pill tone={TONE[kind]}>{t(`plain.tag.${kind}`)}</Pill>
      <Link to={to} className="plain-how">{t("plain.howWeKnow")}</Link>
    </p>
  );
}
