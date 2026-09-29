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
  tokyo: {id: "IRqfQCgELX4", by: "Clarence E. Hsu", alt: "a crowded city intersection at night in Tokyo, from above"},
  tokyoHighway: {id: "VTaATSuMSP8", by: "Jonathan Ikemura", alt: "an illuminated highway interchange at night in Tokyo"},
  interchange: {id: "NCOYAer0vLw", by: "Paddma Sambhav", alt: "a highway interchange at night, light trails of traffic"},
  nairobi: {id: "H1Z6DxyVYbE", by: "Michael Njoroge", alt: "a busy city street in Nairobi"},
  lagos: {id: "cFT_Xq4XyA0", by: "Opeyemi Adisa", alt: "Idumota Avenue in Lagos, filled with traffic"},
  jakarta: {id: "tPAKmlG356Y", by: "Muhamad Daffa Rial", alt: "rush hour on an elevated highway in Jakarta"},
  newyork: {id: "00pM5WzCzR8", by: "Massimiliano Morosinotto", alt: "the New York skyline with the Brooklyn Bridge at dusk"},
  shibuya: {id: "RDlhSZR4SR8", by: "Sarmat Batagov", alt: "Shibuya Crossing at night from a skyscraper"},
} as const;

export type PhotoKey = keyof typeof PHOTOS;
export const photoUrl = (k: PhotoKey) => `/photos/${PHOTOS[k].id}.jpg`;
export const photoPage = (k: PhotoKey) => `https://unsplash.com/photos/${PHOTOS[k].id}`;
