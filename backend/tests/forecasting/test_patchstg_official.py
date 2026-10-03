"""The PatchSTG switch translates the authors' config exactly and never alters their code."""
import inspect

import pytest

from app.forecasting.training import patchstg_official as po


def test_config_translation_matches_the_authors_argparse(tmp_path):
    conf = tmp_path / "SD.conf"
    conf.write_text("[file]\ntraffic = ./data/SD/flowsd.npz\nmeta = ./data/SD/sd_meta.csv\nadj = ./data/SD/adj.npy\n"
                    "model = ./cpt/sd_model\nlog = ./log/sd_log\n[data]\ninput_len = 12\noutput_len = 12\ntrain_ratio = 0.6\n"
                    "val_ratio = 0.2\ntest_ratio = 0.2\n[train]\ncuda = 0\nmax_epoch = 50\nbatch_size = 16\nlearning_rate = 0.002\n"
                    "weight_decay = 0.0001\nseed = 4096\n[param]\nfactors = 32\nlayers = 5\ntps = 12\ntpn = 1\nrecur = 9\nsps = 2\n"
                    "spn = 512\nnodes = 716\ntod = 96\ndow = 7\nid = 64\nnd = 64\ntd = 32\ndd = 32\n")
    a = po.official_args(conf, num_workers=0)
    assert a["node_num"] == 716 and a["spa_patchnum"] == 512 and a["recur_times"] == 9 and a["tem_patchsize"] == 12
    assert a["learning_rate"] == 0.002 and a["cuda"] == "0" and a["model_file"] == "./cpt/sd_model" and a["num_workers"] == 0
    assert set(a) == set(po._ARGS) | {"num_workers"}                 # every name the authors' Solver reads, nothing else


def test_published_table_and_regions_are_the_papers():
    assert po.REGIONS == {"SD": 716, "GBA": 2352, "GLA": 3834, "CA": 8600}
    assert po.PUBLISHED["SD"] == (16.90, 29.27, 11.23) and po.PUBLISHED["CA"] == (17.35, 29.79, 12.79)


def test_switch_is_small_and_imports_the_authors_module_unchanged():
    src = inspect.getsource(po)
    assert len(src.splitlines()) < 200
    assert "import main as official" in src and "solver.test()" in src
    assert "def train" not in src and "class PatchSTG" not in src         # nothing of theirs re-implemented here


@pytest.mark.skipif(not po.REPO.exists(), reason="official clone absent on this machine")
def test_official_clone_is_the_pinned_mit_release():
    assert (po.REPO / "LICENSE").read_text().startswith("MIT License")
    assert (po.REPO / "config" / "SD.conf").exists() and (po.REPO / "data" / "SD" / "sd_meta.csv").exists()
