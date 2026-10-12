"""Shared dependencies for HTTP adapters."""
from __future__ import annotations

import sys
from core.common import evidence_paths as config


def _city_bits():
    """Imported lazily so the dashboard still starts if the research deps are absent."""
    import sys
    sys.path.insert(0, str(config.REPO))
    from core.common.data.datasets import catalog
    from core.common.data.cities import registry
    return registry, catalog
