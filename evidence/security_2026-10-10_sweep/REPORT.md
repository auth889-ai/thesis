# Read-only sweep after the npm backdoor (2026-10-10 ~04:15 +06)

Timeline: 23:31:06 pnpm store index written (a `pnpm install`, most likely in the malicious repository) → 23:32:20-26 `pip install`
portalocker 4.4.0, pyzipper 0.4.0 (+ pycryptodomex 3.24.0) into Miniconda's base Python → 23:32:22 `/tmp/.amFubmF0dWxmZXJkb3VzZXZh`
(base64 of the user name; contains 1791480742149 = that moment in ms) → 23:32:23 `/opt/homebrew/lib/node_modules/npm/lib/cli.js`
injected (1.4 MB obfuscated line 14, padded with spaces) → every npm/npx/yarn call started a loader to 193.247.144.38 until 04:06.

| Check | Result |
|---|---|
| npm `cli.js` | **was injected**; `brew reinstall node` restored it (407 bytes, no long line, no marker) |
| `~/.node_modules` (socket.io-client, rebuilt 02:53 by PID 7354) | deleted with the owner's yes |
| Marker / IP in files changed after 8 Oct 23:00: /opt/homebrew (6 007), /usr/local (0), conda site-packages (599), ~/.vscode/extensions (30), VS Code User (22), corepack (2), ~/.npm (71); ~/.yarn, ~/.config/yarn absent | **0 hits** (scanned_counts.txt) |
| Changed JS with lines > 20 000 chars or long space runs | only npm's own minified files (reinstalled 04:11) and the Claude Code extension: normal minified bundles |
| Python startup hooks (.pth, sitecustomize, usercustomize) changed since 8 Oct | none |
| **Python packages installed by the loader** | pyzipper, portalocker, pycryptodomex in `~/miniconda3/lib/python3.13/site-packages` (pip, "requested directly", 23:32:20-26). Their files are the published packages' names; no payload script found on disk (it probably ran from memory) |
| **/tmp marker and lock files** | `/tmp/.amFubmF0dWxmZXJkb3VzZXZh` (13 bytes, a timestamp), `/tmp/tmp7A863DD1.tmp`, `/tmp/tmp7A863DD3.tmp` (empty, portalocker-style locks) |
| Running processes | no loader, no unknown python/node (my stray run_veins.py stopped) |
| Git hooks in 128 repositories under home (depth 6), core.hooksPath | no non-sample hook, no hooksPath |
| `~/.gitconfig` | changed 23:19 (before the infection): git-lfs and gh credential helper only |
| This repository's package files | `frontend/package.json`/`package-lock.json` last changed 7 Oct 07:07 (before; Ferrostar etc., recorded in HANDOFF); `frontend/map/package.json`, `yarn.lock` (9 Oct, untracked) identical to Headway at d0b994e; all lockfile sources are registry.npmjs.org / registry.yarnpkg.com; no socket.io-client |
| pnpm (Homebrew) | covered by the /opt/homebrew sweep, no hit |
