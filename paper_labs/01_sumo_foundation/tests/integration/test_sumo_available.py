import shutil, pytest

def test_sumo_binary_available():
    if not shutil.which('sumo'):
        pytest.skip('SUMO not installed in this environment; required in Colab execution gate')
    assert shutil.which('netconvert')
