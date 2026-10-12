# DhakaFlow Nexus — rules for every session

## What this project is
An undergraduate research thesis (IUT CSE, Networking Research Group) on road traffic,
combining machine learning and networking. The web app is city-agnostic: it must work
for any city in the world. Dhaka is the first and main case study, not the only target.
Research correctness matters more than polish.

## City-agnostic design rules
1. Never hard-code a city. All city-specific values (map area, SUMO network, time zone,
   languages, emergency numbers, units, vehicle classes, local events like holidays)
   live in config/cities/<city_id>.yaml.
2. Every pipeline must run for any city that has a config file, starting from
   OpenStreetMap data. Dhaka, Los Angeles (METR-LA) and Berlin (Berlin V2X) are the
   evaluation cities.
3. City-specific features (for example rickshaw and CNG modes, Eid travel, monsoon
   waterlogging) are optional plugins enabled per city in its config.
4. If a city lacks data for a feature, the app says "no data for this city" instead of
   guessing or silently falling back to another city's model.
5. Results must always state which city and dataset they come from. Never present a
   result from one city as if it holds for another.

## Fidelity rules (never break these)
1. Never invent, estimate or "fill in" a result. Every number shown in the app or the
   thesis must come from a run whose log and output hash are saved under evidence/.
2. When reusing a paper or GitHub repo, record in third_party/SOURCES.md: repo URL,
   exact commit SHA, license, paper title and venue, and which files we used or changed.
3. Reproduce the original repo's own result first, unchanged, before adapting it.
   Report our number next to the published number.
4. If a repo's license is missing or incompatible with our use, stop and tell me
   before copying any of its code.
5. Do not add new papers, features or pages beyond the phase prompt. If you think
   something should be added, write it in docs/proposals.md and ask me.

## Working rules
- Never create, switch or merge branches; work in the current working tree until the owner commits at the end.
- Start every phase in plan mode and wait for my approval.
- Every phase ends with: passing tests, a README section with exact run commands,
  and evidence entries for every result.
- User-facing text goes through the i18n system. Ship Bangla and English; adding a
  language must need only a new translation file.

## Speed rules
- During a step, run only the tests for the changed files. Run the full suite once per phase.
- Browser checks: once per step, on one city.
- Ask only blocking questions.
- Keep reports short.

## Plain language rule (everyday pages: Home, 3D City, Add city, Emergency, Offline alerts, Settings)
1. Each result appears as one short sentence a non-expert understands, then a small tag (Simulation, Real recorded,
   or Forecast) and a "How we know →" link to the matching Research page. No seeds, ±, crash counts, model, protocol
   or report names, file names or hashes on everyday pages.
2. The full tables, sources and caveats live on Research (/lab), unchanged. Nothing is hidden, only placed where
   reviewers look.
3. No developer wording on everyday pages: no "Sampling stopped" chip, no "Every answer is computed…" footer, no
   "generated, uncalibrated" or "fitted to counts on a few sections"; plain words, or move it to Research.
4. Emergency: numbers first, then the ambulance sentence with its tag and a "Watch it in 3D" button, then
   "Crash SOS: coming soon".
5. Every plain sentence is computed from the same results file as the Research table, never typed in; a test checks
   its number matches the table.

## Privacy and safety rules
- Design to the strictest common standard (GDPR level): opt-in only, hashed device IDs,
  raw positions deleted after 24 hours, no data sold or shared.
- Never send real SMS, calls or alerts to real people or emergency numbers during
  development. Use test contacts and a clearly marked TEST mode.
- Emergency numbers come only from the city config and are shown, never auto-dialled.

## AWS cost rules (never break these)
1. Before launching anything paid, state the instance type, expected hours and
   estimated cost, and wait for my approval.
2. Prefer spot instances for training and simulation sweeps. Every job must save
   checkpoints to S3 so a spot interruption loses little work.
3. Every instance and job gets tags: project=dhakaflow, phase=<phase name>.
4. Every instance must shut itself down when its job ends (shutdown command at the
   end of the script). Never leave a GPU instance idle.
5. Default region ap-south-1 (Mumbai, closest to Dhaka) unless a service is not
   available there.
   Exception: model training stays in us-east-1, where the training bucket, the
   PyTorch GPU image and the GPU quota already are.
6. At the end of every session, list all running instances and ask me before
   leaving any of them on.
7. Never use real phone numbers outside the SNS SMS sandbox.
