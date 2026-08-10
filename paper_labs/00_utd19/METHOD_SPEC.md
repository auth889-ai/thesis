# METHOD_SPEC — Loder et al. 2019, "Understanding traffic capacity of urban networks"

Every item is tagged **PUBLISHED** (stated in the paper/companion refs),
**INFERRED** (follows from the text but not stated verbatim),
**ASSUMED** (our choice where the material is silent), or
**UNKNOWN FROM AVAILABLE MATERIAL**.

Source of paper text: `paper/loder2019_fulltext.xml` (complete JATS full text incl. Methods).
Supplementary Information (107 network figures, robustness Tables 2–4) is hosted at the DOI;
it must be downloaded in Colab (Nature blocks non-browser downloads from this machine) —
until then, items depending on it are marked accordingly.

## 1. Research questions — PUBLISHED

1. Where is the critical point (n\*, P\*) of an urban network's MFD, measured
   empirically across many cities? (Introduction ¶3, ¶5)
2. Which measurable topology factors explain the variation in critical points?
   (Introduction ¶5; Results)

## 2. Required variables

| Variable | Meaning | Units | Status |
|---|---|---|---|
| q_i(t) | detector flow, interval ~300 s | veh/h | PUBLISHED (Methods "Initial dataset") |
| o_i(t) | detector occupancy | fraction | PUBLISHED |
| n | accumulation (per km²) | veh km⁻² | PUBLISHED (Introduction ¶4) |
| P(n) | production (per km²) | veh-km h⁻¹ km⁻² | PUBLISHED |
| v = P/n | average network speed | km/h | PUBLISHED |
| (n\*, P\*, v\*) | critical point | as above | PUBLISHED |
| L | network lane length | lane-km | PUBLISHED (Methods "MFD estimation" ¶3) |
| A | regional network area | km² | PUBLISHED (Methods "Derivation of ... topology variables") |
| R = L/A | road network density | lane-km km⁻² | PUBLISHED |
| b_c | mean betweenness centrality | – | PUBLISHED |
| I = #LSA/L/l̄ | intersection spacing variable | LSA km⁻¹ | PUBLISHED |
| B = L_BN/HW/A | bus production density | bus-km h⁻¹ km⁻² | PUBLISHED |

## 3. Data preparation — detector side

1. **Detector road-class filter**: only detectors on OSM trunk, primary,
   secondary, tertiary roads. — PUBLISHED (Methods "Initial dataset")
2. **Error filtering**: remove "obvious errors" (e.g., flow>0 with occupancy=0),
   "obvious outliers" (ref 35), "obvious noise" (ref 36 TRAMO/SEATS). —
   PUBLISHED that filtering happened; the **exact thresholds/parameters are
   UNKNOWN FROM AVAILABLE MATERIAL** (paper cites methods but gives no values).
   Our reconstruction will implement explicit, documented rules and report
   per-rule removal counts (see DATA_SPEC §6) — MODIFIED_BY_US by necessity.
3. **Regional network definition**: heuristic, typically <10 km², roughly
   homogeneous congestion. — PUBLISHED as heuristic; the actual polygon per
   network is only visible in Supplementary Figs. 1–107; machine-readable
   partitions are **UNKNOWN FROM AVAILABLE MATERIAL**. UTD19's released
   detector metadata may or may not encode these regions — to be checked in the
   Colab audit (DATA_SPEC §5).

## 4. MFD estimation — PUBLISHED (Methods "MFD estimation and calibration")

1. **Loops method** (refs 12, 37): network sample mean over detectors, per
   interval t: q̄(t) = (1/N_det)Σ q_i(t); ō(t) = (1/N_det)Σ o_i(t), with
   correction for detector-location bias (refs 37–39). The paper does not give
   the explicit bias-correction formula — **UNKNOWN FROM AVAILABLE MATERIAL**
   (would require ref 39, Ambühl et al. 2019 TRR).
2. **Re-sampling** (ref 17): 300 draws, each of 80% of detectors; PUBLISHED
   (draw count and rate stated). Purpose: isolate the boundary of feasible
   states from demand irregularities. Sampling with/without replacement is not
   stated in this paper — INFERRED from ref 17 title/abstract as sampling of
   detector subsets without replacement within a draw; final choice documented
   in ASSUMPTIONS.md.
3. **Speed treatment / occupancy rescaling** (two-step):
   - Step 1 — rescale each detector's occupancy so that its free-flow q/o
     matches the expected speed at that location (ref 42). PUBLISHED as
     procedure; the source of "average speed expected at that location" (speed
     limit? fclass mean?) is not fully specified — INFERRED options documented
     in ASSUMPTIONS.md.
   - Step 2 — calibrate MFD speeds to Google Directions API references (1000
     random OD pairs, 1–6 km, excluding freeways, fastest observed hour).
     PUBLISHED as procedure but **UNREPRODUCIBLE_FROM_AVAILABLE_HISTORICAL_INPUTS**:
     the 2017–2019 Google queries cannot be re-issued. Lab 00 therefore produces
     an `UNCALIBRATED_ANALYSIS` only; any future `CALIBRATED_ANALYSIS` with
     modern APIs would be a separate, clearly-labelled variant (Scientific
     Correction 4).
4. **Scaling to production/accumulation**: multiply per-lane flow/density by
   network length L; normalize by area A. PUBLISHED. Requires L per regional
   network from OSM — for Lab 00 smoke test we stay in per-lane flow vs
   occupancy space (RAW_SANITY_MFD) and defer L-scaling to the
   PAPER_FAITHFUL_MFD stage.

## 5. Critical-point estimation — PUBLISHED (Methods "Critical point estimation")

1. Extract upper bound: flow's **95th–97.5th percentile within density bins**
   ("uppermost 20-quantile", quantile-regression approach, ref 43). Bin width is
   **UNKNOWN FROM AVAILABLE MATERIAL** — will be an ASSUMED parameter with
   sensitivity check.
2. Fit the **MFD functional form of ref 18** (Ambühl, Loder, Bliemer, Menendez,
   Axhausen, *A functional form for the macroscopic fundamental diagram with a
   physical meaning*, Transp. Res. B) to the upper bound by **nonlinear least
   squares**. The form (from ref 18) is the smooth log-sum-exp lower envelope of
   three physical branches (free-flow speed, capacity plateau, backward wave):

       q(k) = −λ · ln( exp(−v_f·k/λ) + exp(−Q/λ) + exp(−(κ−k)·w/λ) )

   with v_f free-flow speed, Q capacity plateau, κ jam density, w backward-wave
   speed, λ smoothing parameter. — PUBLISHED in ref 18 (form to be re-verified
   against the ref-18 paper in the reconstruction stage before use; equation
   here reproduced from that companion paper, tag: INFERRED until re-verified).
3. Critical point = maximum of the fitted function. PUBLISHED.

## 6. Observation weights — PUBLISHED (Methods "Calculation of observation weights")

    w_i = log(N) / (P*_95 − P*_5) · exp( −(s_high − s_low)/s_mean )

- N = number of observed intervals; P*_95, P*_5 = production quantiles at n\*;
  s_mean/s_low/s_high = speed-calibration scalar statistics (defined in Methods).
- Only needed for the cross-network regression (out of Lab 00 smoke scope).

## 7. Regression analysis — PUBLISHED (Results; Table 1) — OUT OF LAB-00 SMOKE SCOPE

Two-stage least squares; n\* endogenous (robust score test p=0.000); instruments
R, b_c, R×I; B in capacity equation; errors clustered by city; observations
weighted by w_i. Reported: Adj. R² = 0.88 (n\* eq.) / 0.91 (P\* eq.);
elasticity ∂log P\*/∂log n\* = 0.968 [0.828, 1.107] (≈1);
∂log n\*/∂log R = 0.839 [0.727, 0.950] (<1, sublinear).

## 8. Key reported quantities usable as reproduction targets

| Quantity | Published value | Feasibility for us |
|---|---|---|
| P̄\* over 107 networks | 12,236 ± 5,513 veh-km h⁻¹ km⁻² | needs all networks + L-scaling — later stage |
| n̄\* | 653 ± 308 veh km⁻² | same |
| mean critical speed | 18.8 km/h (Fig. 2b) | needs calibrated speeds — blocked by Google-calibration issue |
| P\* vs n\* correlation | R² ≈ 0.91–0.92 | later stage |
| Per-network MFD shape (Supp. Figs 1–107) | ∩-shaped boundary | **most feasible first target**: qualitative + critical-point comparison for one city once Supplementary is downloaded |
| Table 1 coefficients | see paper | requires OSM topology pipeline — out of Lab 00 |

## 9. Analysis procedure for Lab 00 (our reconstruction plan)

Stage 0 (smoke, this lab iteration): city audit → select city → validate →
RAW_SANITY_MFD (mean flow vs mean occupancy scatter colored by time) — explicitly
NOT the paper's MFD.
Stage 1 (paper-faithful, after smoke approval): detector filtering per §3,
re-sampling per §4.2, occupancy rescaling §4.3 step 1 (uncalibrated), upper-bound
extraction §5.1, functional-form fit §5.2, critical point §5.3 → PAPER_FAITHFUL_MFD
(UNCALIBRATED_ANALYSIS).
