from pathlib import Path

import pytest

from tiger_guides.config import load_config, SpeciesOption


def test_load_default_config(tmp_path):
    config = load_config(None, SpeciesOption("mouse"))
    assert config["species"] == "mus_musculus"
    assert "offtarget" in config


def test_invalid_species():
    with pytest.raises(ValueError):
        SpeciesOption("alien")


def test_custom_config(tmp_path):
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("project_name: test\n")
    config = load_config(cfg, SpeciesOption("human"))
    assert config["species"] == "homo_sapiens"
