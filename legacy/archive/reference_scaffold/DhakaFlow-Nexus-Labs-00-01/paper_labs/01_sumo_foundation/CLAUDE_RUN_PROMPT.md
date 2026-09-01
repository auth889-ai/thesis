# Claude prompt — run Lab 01 in Colab

Start only after Lab 00 is approved PASS/PARTIAL with documented limitations.

1. Read all Lab 01 specs/resources first.
2. Run the Colab notebook top-to-bottom.
3. Install SUMO in Colab and record `sumo --version` / `netconvert --version`.
4. Fetch the canonical paper from DLR and the official `DLR-TS/sumo-scenarios` repo.
5. Record the exact upstream commit SHA.
6. Build/validate the deterministic unit intersection.
7. Run Fixed-Time, Actuated, Max-Pressure on identical demand.
8. Ensure yellow/all-red/min-green safety transitions.
9. Run tests and inspect tripinfo + queue outputs.
10. Run the official Bologna/Acosta scenario from the official repo and collect baseline metrics without rewriting upstream scenario files.
11. If current SUMO breaks an old official scenario, document the compatibility issue and make the smallest wrapper/compatibility fix outside upstream files.
12. Never replace official real Bologna demand with random demand and still call it reproduction.

Stop with `LAB 01 STATUS: PASS / PARTIAL / FAIL`, exact Colab URL, SUMO version, upstream SHA, outputs, benchmark table and unresolved issues. Do not start Lab 02 automatically.
