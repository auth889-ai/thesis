/** Pure part of the along-the-drive download: which planned route steps are due now (each once, none planned empty). */
export function dueSteps(stepEnds: number[], travelledM: number, fired: Set<number>, perStep: number[]): number[] {
  return stepEnds.map((end, i) => i).filter((i) => perStep[i] > 0 && !fired.has(i) && travelledM >= (i === 0 ? 0 : stepEnds[i - 1]));
}
