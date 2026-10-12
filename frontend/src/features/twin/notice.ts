/** The simulated twin's notice, built from what the scene and the city actually are: real map data, which vehicle mix, which demand, and that nothing is a live measurement. */
export type NoticeScene = {demand?: {label?: string; calibrated_to?: string | null}} | undefined;
export type NoticeCity = {vehicle_mix?: {source: string; citation: string} | null} | null | undefined;

export function noticeFor(scene: NoticeScene, city: NoticeCity, t: (k: string, v?: Record<string, string | number>) => string, research = true): string {
  if (!research) {                                   // the everyday page: plain words, no calibration string or citation (CLAUDE.md, plain language rule)
    return [t("twin.notice.map"), city?.vehicle_mix ? t("twin.notice.plainMix") : t("twin.notice.oneClassPlain"),
            scene?.demand?.calibrated_to ? t("twin.notice.plainCalibrated") : t("twin.notice.plainUncalibrated"), t("twin.notice.notLive")].join(" ");
  }
  const mix = city?.vehicle_mix ? t("twin.notice.mix", {source: city.vehicle_mix.source}) : t("twin.notice.oneClass");
  const demand = scene?.demand?.calibrated_to ? t("twin.notice.calibrated", {calibration: scene.demand.calibrated_to}) : t("twin.notice.uncalibrated");
  return [t("twin.notice.map"), mix, demand, t("twin.notice.notLive")].join(" ");
}
