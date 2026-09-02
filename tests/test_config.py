from argparse import Namespace
from pathlib import Path

from wheel_bot.config import apply_cli_overrides, config_from_mapping, load_yaml, _as_float_percent


def _args(**kwargs) -> Namespace:
    base = dict(
        ticker=None,
        otm_percent=None,
        put_otm_percent=None,
        call_otm_percent=None,
        quantity=None,
        dte=None,
        host=None,
        port=None,
        client_id=None,
        dry_run=None,
        state_path=None,
        config=None,
    )
    base.update(kwargs)
    return Namespace(**base)


def test_percent_accepts_ratio_or_whole_number():
    assert _as_float_percent(0.03) == 0.03
    assert _as_float_percent(3) == 0.03
    assert _as_float_percent("5") == 0.05


def test_example_yaml_loads(tmp_path: Path):
    # repo-relative example
    data = load_yaml(Path("config.example.yaml"))
    cfg = config_from_mapping(data)
    assert cfg.ticker == "SPY"
    assert cfg.otm_percent == 0.03
    assert cfg.put_percent == 0.03
    assert cfg.call_percent == 0.03
    assert cfg.dry_run is True
    assert cfg.ib.port == 7497


def test_cli_overrides_ticker_and_percent():
    cfg = config_from_mapping({"ticker": "SPY", "otm_percent": 0.03})
    out = apply_cli_overrides(cfg, _args(ticker="qqq", otm_percent=5))
    assert out.ticker == "QQQ"
    assert out.otm_percent == 0.05
