"""Tests for the command-line interface (no network: the fetchers are replaced)."""

import pandas as pd
import pytest

from en630 import cli


def test_reproduce_prints_the_summary_and_writes_a_file(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert cli.main(["reproduce"]) == 0
    out = capsys.readouterr().out
    assert "35 of 42 figures reproduce" in out
    assert (tmp_path / "outputs" / "final_report_reproduction.csv").exists()


def test_simulate_reports_the_annual_results(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert cli.main(["simulate", "--dishes", "14", "--storage", "1000", "--hourly"]) == 0
    out = capsys.readouterr().out
    assert "solar share" in out and "cylinders displaced" in out
    hourly = pd.read_csv(tmp_path / "outputs" / "hourly.csv")
    assert len(hourly) == 8760


def test_sweep_finds_a_best_design_and_writes_the_grid(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert cli.main(["sweep", "--min-dishes", "6", "--max-dishes", "14", "--step", "4"]) == 0
    assert "best NPV" in capsys.readouterr().out
    grid = pd.read_csv(tmp_path / "outputs" / "sweep.csv")
    assert set(grid.n_dishes) == {6, 10, 14}


def test_fetch_data_calls_both_downloads_unless_told_otherwise(monkeypatch, tmp_path, capsys):
    calls = []
    monkeypatch.setattr(cli, "DATA", tmp_path)
    monkeypatch.setattr(cli, "fetch_pvgis_tmy", lambda site, path: calls.append(("tmy", path)))
    monkeypatch.setattr(cli, "fetch_pvgis_multiyear", lambda site, a, b, path: calls.append(("multi", path)))
    assert cli.main(["fetch-data"]) == 0
    assert [c[0] for c in calls] == ["tmy", "multi"]
    calls.clear()
    assert cli.main(["fetch-data", "--tmy-only"]) == 0
    assert [c[0] for c in calls] == ["tmy"]


def test_a_command_is_required():
    with pytest.raises(SystemExit):
        cli.main([])


def test_unknown_command_is_rejected():
    with pytest.raises(SystemExit):
        cli.main(["optimise"])
