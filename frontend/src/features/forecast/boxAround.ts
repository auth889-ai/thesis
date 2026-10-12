/** [south, west, north, east] of a square of `size` degrees around a centre. */
export const boxAround = (lon: number, lat: number, size: number) => [lat - size / 2, lon - size / 2, lat + size / 2, lon + size / 2].map((x) => +x.toFixed(5));
