from pathlib import Path

from market_briefing import cli


def test_cli_data_root_precedence(monkeypatch, tmp_path, capsys):
    captured = []
    monkeypatch.setattr(cli, "_generate", lambda args, *_: captured.append(args.data_root) or 0)
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    assert cli.main(["research"]) == 0
    assert captured[-1] == tmp_path / "quant-market-briefing"
    explicit = tmp_path / "explicit"
    assert cli.main(["research", "--data-root", str(explicit)]) == 0
    assert captured[-1] == explicit
    assert not capsys.readouterr().err
    monkeypatch.delenv("DATA_ROOT")
    assert cli.main(["research"]) == 0
    assert captured[-1] == Path.home() / "data" / "quant-market-briefing"
    assert "DATA_ROOT" in capsys.readouterr().err
