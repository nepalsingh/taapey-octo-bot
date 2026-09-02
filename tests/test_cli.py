from wheel_bot.cli import main


def test_simulate_sell_put(capsys):
    rc = main(
        [
            "--simulate",
            "--ticker",
            "SPY",
            "--otm-percent",
            "3",
            "--price",
            "500",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "SELL_PUT" in out
    assert "485" in out
    assert "SPY" in out


def test_simulate_assigned_sells_call(capsys):
    rc = main(
        [
            "--simulate",
            "--ticker",
            "QQQ",
            "--otm-percent",
            "0.03",
            "--price",
            "490",
            "--previous-close",
            "500",
            "--assigned",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "SELL_CALL" in out
    assert "515" in out
    assert "QQQ" in out
