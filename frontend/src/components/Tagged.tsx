import {useI18n} from "@/i18n";

/** The tag every traffic value arrives with (core/common/tag.py): measured, simulated, or forecast. */
export type Tag = {kind: "real" | "simulated" | "forecast"; source?: string; as_of?: string; calibrated_to?: string; basis?: string; model?: string; issued_at?: string;
                   based_on?: string; uncertainty?: string; covers_share_of_length?: number; rest?: string; phones_at_least?: number; recorded?: boolean; label?: string; citation?: string; vehicles?: number; stretch_m?: number};
export type TaggedValue = {value: number; unit: string; tag: Tag; range?: [number, number]};

const clock = (iso: string | undefined, lang: string) => { const d = iso ? new Date(iso) : null; return d && !Number.isNaN(d.getTime()) ? d.toLocaleString(lang, {dateStyle: "medium", timeStyle: "short"}) : iso ?? ""; };

/** The words of a tag. Real: who measured it and the time it refers to. Simulated: what it is calibrated to. Forecast: the model, its basis and how sure. */
export function tagWords(tag: Tag, t: (k: string, v?: Record<string, string | number>) => string, lang: string): string | null {
  if (tag?.kind === "real" && tag.recorded) return t("tag.recorded", {source: tag.source ?? "", time: tag.as_of ?? ""});
  if (tag?.kind === "real") return t("tag.real", {source: tag.source ?? "", time: clock(tag.as_of, lang)});
  if (tag?.kind === "simulated") return t(tag.calibrated_to === "uncalibrated" ? "tag.simulatedUncalibrated" : "tag.simulated", {basis: tag.basis ?? "", calibration: tag.calibrated_to ?? ""});
  if (tag?.kind === "forecast") return t("tag.forecast", {model: tag.model ?? "", basis: tag.based_on ?? "", uncertainty: tag.uncertainty ?? ""});
  return null;
}

/** A value with its tag beside it. A value that arrives without a tag is not shown. */
export function Tagged({v, digits = 0}: {v: TaggedValue | null | undefined; digits?: number}) {
  const {t, lang} = useI18n();
  const words = v ? tagWords(v.tag, t, lang) : null;
  if (!v || !words) return null;
  return (
    <span className={`tagged tagged-${v.tag.kind}`}>
      <b>{v.value.toLocaleString(lang, {maximumFractionDigits: digits})} {v.unit}</b>
      {v.range && <span className="tagged-range"> ({v.range[0].toLocaleString(lang, {maximumFractionDigits: digits})}–{v.range[1].toLocaleString(lang, {maximumFractionDigits: digits})})</span>}
      <span className="tagged-kind">{t(v.tag.recorded ? "tag.kind.recorded" : `tag.kind.${v.tag.kind}`)}</span>
      <span className="tagged-words">{words}</span>
    </span>
  );
}
