/**
 * How worldwide buildings are drawn: the height each gets and its colour. No map library here, so the rule can be tested.
 * A building with a recorded height is coloured by it; one without is drawn at an assumed height in one separate colour
 * and called "estimated height".
 */
import type {ExpressionSpecification} from "maplibre-gl";

export type Buildings = {url: string; release: string; attribution: string; source_layer: string; minzoom: number; heights: {assumed_storey_m: number; assumed_default_m: number}};

export const ESTIMATED_COLOUR = "#d6cdc2";
/** Height in metres -> colour, for recorded heights only. */
export const HEIGHT_RAMP: [number, string][] = [[0, "#dbe7f3"], [15, "#a9c4e0"], [40, "#6f97c6"], [100, "#3f67a3"], [250, "#22396b"]];
export const hasRecordedHeight: ExpressionSpecification = ["has", "height"];

/** The drawn height: recorded height; else recorded floors x the assumed storey; else the assumed default. */
export function heightExpression(b: Buildings): ExpressionSpecification {
  return ["case", hasRecordedHeight, ["to-number", ["get", "height"]],
          ["has", "num_floors"], ["*", ["to-number", ["get", "num_floors"]], b.heights.assumed_storey_m],
          b.heights.assumed_default_m] as ExpressionSpecification;
}

export function colourExpression(): ExpressionSpecification {
  return ["case", hasRecordedHeight, ["interpolate", ["linear"], ["to-number", ["get", "height"]], ...HEIGHT_RAMP.flat()], ESTIMATED_COLOUR] as ExpressionSpecification;
}
