import {USER_ID} from "@/features/assistant/types";
import type {Point} from "@/features/today/HomeMap";
import {api} from "@/lib/api";
import {savePack, ZOOMS, ZOOMS_LOW_DATA} from "@/lib/pack";
import {lowData} from "@/lib/settings";

/** Save what a drive needs before it starts, so it goes on where the signal is weak or gone: the route answer, the start-up answers
 * and the map tiles along the line (fewer zooms in low-data mode). Returns the bytes saved. Pure in its inputs; tested. */
export async function saveForWeakSignal(cityId: string, origin: Point, destination: Point, geometry: number[][], save = savePack): Promise<number> {
  const o = `${origin.lat},${origin.lon}`, d = `${destination.lat},${destination.lon}`;
  const urls = api.packUrls(cityId, o, d, "car", USER_ID).map((u) => new URL(u, location.origin).toString());
  const got = await save(cityId, {origin, destination, profile: "car"}, geometry, urls, lowData() ? ZOOMS_LOW_DATA : ZOOMS);
  return got.tile_bytes + got.api_bytes + got.asset_bytes;
}

