from pathlib import Path

import pytest
from pydantic import ValidationError

from zerodhatrades.config import Condition, load_config


def test_example_config_valid():
    cfg = load_config(Path(__file__).parent.parent / "config" / "strategies.example.yaml")
    assert cfg.mode == "paper"


def test_bad_sma_params():
    with pytest.raises(ValidationError):
        Condition(type="sma_cross_up", fast=21, slow=9)
