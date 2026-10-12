# nose 1.3.7 (pinned by sumo-web3d) does not import on Python 3.13; its eq_ is a plain equality assert.
def eq_(a, b, msg=None):
    assert a == b, msg or f"{a!r} != {b!r}"
import unittest
assert_raises = unittest.TestCase().assertRaises
