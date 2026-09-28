"""Compatibility package: the web application moved to backend/ (FastAPI) and frontend/; the old
flat module names under dashboard/backend/ are kept as aliases of the canonical modules so research
code and tests written against them keep importing the SAME objects (see dashboard/backend/__init__)."""
