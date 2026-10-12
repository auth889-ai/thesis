# Motorbike against car on Dhaka trips (owner request, 2026-10-07)

- **Source:** the hosted app's own routing server (Valhalla, Dhaka), asked through `/api/navigate/dhaka/route` with the same two points per trip. First route per costing. Raw output: `motorbike_vs_car.txt`.
- **Result:** the routes were identical (same km, minutes and line) on 6 of 8 trips.
- **Where they differ:** Uttara → Motijheel and Airport → Sadarghat. On both, the motorbike route is shorter but slower:
  - Uttara → Motijheel: 20.05 km, 88.9 min, against the car's 22.25 km, 81.2 min;
  - Airport → Sadarghat: 17.89 km, 78.7 min, against 19.88 km, 69.6 min.
- **Decision:** the motorbike choice is **kept**, because it does change the route on some trips. When the server gives the motorbike exactly the car's route, the page now says so in one sentence (`home.route.sameAsCar`) instead of implying the choice changed something.
- **Not checked:** why the long trips differ. One possibility is motorcycle access tags on a highway, such as the elevated expressway, but that has not been verified, so it is not claimed.
- **Regression test:** `frontend/src/features/today/trip.test.ts` (`sameFirstRoute`).

| Trip | Car (km, min, line) | Motorbike (km, min, line) | Same |
|---|---|---|---|
| Banani->DMCH | 9.221, 40.62, 'ad09193098' | 9.221, 40.62, 'ad09193098' | yes |
| Uttara->Motijheel | 22.248, 81.21, 'f8275f393c' | 20.051, 88.89, 'a7f73147d1' | no |
| Mirpur10->Gulshan1 | 9.751, 44.18, 'cf1e2f4ed1' | 9.751, 44.18, 'cf1e2f4ed1' | yes |
| Mohammadpur->Jatrabari | 13.601, 57.3, '0964fa8875' | 13.601, 57.3, '0964fa8875' | yes |
| Farmgate->Shahbagh | 2.684, 11.32, 'f31419842c' | 2.684, 11.32, 'f31419842c' | yes |
| Dhanmondi27->Badda | 9.343, 41.96, 'e74babe04a' | 9.343, 41.96, 'e74babe04a' | yes |
| Airport->Sadarghat | 19.881, 69.61, '174a1b09d1' | 17.888, 78.73, '1d2af1ed6e' | no |
| Tejgaon->Old Dhaka | 6.446, 30.87, '6df49a1f04' | 6.446, 30.87, '6df49a1f04' | yes |
