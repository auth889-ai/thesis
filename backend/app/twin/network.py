"""Process-local cache of parsed, static SUMO network geometry."""
_NET_CACHE: dict = {}


def net_for(path) -> "sumolib.net.Net":
    """The parsed SUMO network, read once per process (a 15k-edge network takes seconds to parse)."""
    key = str(path)
    if key not in _NET_CACHE:
        import sumolib
        _NET_CACHE[key] = sumolib.net.readNet(key)
    return _NET_CACHE[key]

