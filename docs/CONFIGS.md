# Configuration Ownership

This directory holds non-secret YAML/JSON/XML settings, not algorithms, datasets
or credentials. Keep local API keys in the gitignored root `.env`.

Perception, tracking, camera and deployment settings include historical work.
Their presence does not establish validated features in the current Scenario A.
Do not create empty subsystem folders or competing configuration copies.

The migration is incomplete: the frozen controller still reads
`src/pipeline/v2x/controller_config.json`, and routing reads
`src/pipeline/routing/routing_config.json`. These paths and contents are preserved
for protocol compatibility. Future moves must update all readers, preserve hashes,
and pass protocol/import tests. A new setting must not silently alter evaluation.
