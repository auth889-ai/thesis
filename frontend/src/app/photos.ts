/** Photographs: Unsplash (free under the Unsplash License), files in public/photos, the photographer credited wherever one is shown. */
export const PHOTOS = {
  bus: {id: "tUXQHNpoEgg", by: "Kabiur Rahman Riyad", alt: "a colourful bus on a Dhaka city street"},
  street: {id: "OP62QfacSTk", by: "Mahibul Hasan Fahim", alt: "a busy Dhaka street filled with traffic"},
  highway: {id: "xULCIysRiBM", by: "Kabiur Rahman Riyad", alt: "a busy highway beside a canal in Dhaka"},
  aerial: {id: "olFpgSOSHfE", by: "Sazzad Aryan", alt: "aerial view of a red bus on a road"},
  night: {id: "NqOInJ-ttqM", by: "Marc-Olivier Jodoin", alt: "long exposure of a road at night"},
  lapse: {id: "56zXu3g8RJE", by: "Jan Valečka", alt: "time-lapse of cars on a road at night"},
  metro: {id: "s_dsxGg4vKI", by: "Muhammad", alt: "a train at a Dhaka metro station"},
  metroCar: {id: "8uLLMHdHM70", by: "Kabiur Rahman Riyad", alt: "commuters inside a crowded metro car"},
  rickshaws: {id: "PoV905Bpaqo", by: "Samiul Haque Bhuyan", alt: "rickshaws and cars on a tree-lined Dhaka street"},
  crossing: {id: "9M1w0mP8CM8", by: "Md. Ashraful Kabir", alt: "a busy Dhaka street with pedestrians and a rickshaw"},
  rest: {id: "bd9i0SzEgBc", by: "Kabiur Rahman Riyad", alt: "a rickshaw driver resting"},
} as const;

export type PhotoKey = keyof typeof PHOTOS;
export const photoUrl = (k: PhotoKey) => `/photos/${PHOTOS[k].id}.jpg`;
export const photoPage = (k: PhotoKey) => `https://unsplash.com/photos/${PHOTOS[k].id}`;
