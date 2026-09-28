"""Shared dependencies for HTTP adapters."""
from __future__ import annotations

import sys
from backend.app import config


def _city_bits():
    """Imported lazily so the dashboard still starts if the research deps are absent."""
    import sys
    sys.path.insert(0, str(config.REPO))
    from traffictwin.data.datasets import catalog
    from traffictwin.data.cities import registry
    return registry, catalog
