"""Unit tests for count_tokens.py."""

from count_tokens import main, parse_log


# --- parse_log ---


def test_parse_log_single_usage_line() -> None:
    """One usage line yields matching totals."""
    lines = ["[query_analyst] usage: input_tokens=852 output_tokens=222 total_tokens=1074\n"]
    summary = parse_log(lines)
    assert summary["calls"] == 1
    assert summary["input"] == 852
    assert summary["output"] == 222
    assert summary["combined"] == 1074
    assert summary["nodes"] == [("query_analyst", 1, 852, 222, 1074)]


def test_parse_log_multiple_nodes_accumulate() -> None:
    """Multiple usage lines across nodes accumulate per-node and globally."""
    lines = [
        "[query_analyst] usage: input_tokens=100 output_tokens=50 total_tokens=150\n",
        "[task_analyzer] usage: input_tokens=200 output_tokens=100 total_tokens=300\n",
        "[query_analyst] usage: input_tokens=10 output_tokens=5 total_tokens=15\n",
    ]
    summary = parse_log(lines)
    assert summary["calls"] == 3
    assert summary["input"] == 310
    assert summary["output"] == 155
    assert summary["combined"] == 465
    # query_analyst has higher combined (165) than task_analyzer (300)? No —
    # task_analyzer combined=300 > query_analyst combined=165, so it sorts first.
    assert summary["nodes"][0][0] == "task_analyzer"
    assert summary["nodes"][0][4] == 300
    assert summary["nodes"][1][0] == "query_analyst"
    assert summary["nodes"][1][4] == 165


def test_parse_log_ignores_non_usage_lines() -> None:
    """Lines without the usage pattern are silently skipped."""
    lines = [
        "=== LIVE STREAM ===\n",
        "[query_analyst] start\n",
        "[query_analyst] usage: input_tokens=852 output_tokens=222 total_tokens=1074\n",
        "The user wants me to research frontier LLM models.\n",
        "[tool-result] node=QueryAnalyst tool=select_query_route completed\n",
    ]
    summary = parse_log(lines)
    assert summary["calls"] == 1
    assert summary["input"] == 852


def test_parse_log_empty_input() -> None:
    """Empty input yields zero calls."""
    summary = parse_log([])
    assert summary["calls"] == 0
    assert summary["input"] == 0
    assert summary["output"] == 0
    assert summary["combined"] == 0
    assert summary["nodes"] == []


def test_parse_log_nodes_sorted_by_combined_descending() -> None:
    """Nodes are sorted by combined tokens, highest first."""
    lines = [
        "[node_a] usage: input_tokens=100 output_tokens=0 total_tokens=100\n",
        "[node_b] usage: input_tokens=500 output_tokens=500 total_tokens=1000\n",
        "[node_c] usage: input_tokens=50 output_tokens=50 total_tokens=100\n",
    ]
    summary = parse_log(lines)
    names = [n[0] for n in summary["nodes"]]
    assert names == ["node_b", "node_a", "node_c"]
    # node_a and node_c tie at 100; stable sort keeps insertion order (a before c).


# --- main (CLI) ---


def test_main_single_file_prints_totals(tmp_path, capsys) -> None:
    """A single file prints header + totals + per-node breakdown."""
    log = tmp_path / "stdout.log"
    log.write_text(
        "[query_analyst] usage: input_tokens=852 output_tokens=222 total_tokens=1074\n"
        "[task_analyzer] usage: input_tokens=200 output_tokens=100 total_tokens=300\n"
        "some other line\n"
    )
    code = main([str(log)])
    out = capsys.readouterr().out
    assert code == 0
    assert str(log) in out
    assert "LLM calls:        2" in out
    assert "1,074" in out  # combined total for query_analyst line... actually total is 1374
    assert "by node:" in out
    assert "query_analyst" in out
    assert "task_analyzer" in out


def test_main_multiple_files_prints_grand_total(tmp_path, capsys) -> None:
    """Two files print two blocks plus a grand total."""
    log1 = tmp_path / "a.log"
    log1.write_text("[node] usage: input_tokens=100 output_tokens=50 total_tokens=150\n")
    log2 = tmp_path / "b.log"
    log2.write_text("[node] usage: input_tokens=200 output_tokens=100 total_tokens=300\n")
    code = main([str(log1), str(log2)])
    out = capsys.readouterr().out
    assert code == 0
    assert "TOTAL (2 files)" in out
    assert "3" in out  # 2 calls
    assert "450" in out  # 150 + 300 combined


def test_main_stdin_when_no_files(capsys, monkeypatch) -> None:
    """No file args → reads stdin."""
    import io

    monkeypatch.setattr(
        "sys.stdin", io.StringIO("[worker] usage: input_tokens=10 output_tokens=5 total_tokens=15\n")
    )
    code = main([])
    out = capsys.readouterr().out
    assert code == 0
    assert "<stdin>" in out
    assert "15" in out


def test_main_no_by_node_skips_breakdown(tmp_path, capsys) -> None:
    """--no-by-node suppresses the per-node section."""
    log = tmp_path / "stdout.log"
    log.write_text("[query_analyst] usage: input_tokens=852 output_tokens=222 total_tokens=1074\n")
    code = main([str(log), "--no-by-node"])
    out = capsys.readouterr().out
    assert code == 0
    assert "by node:" not in out
    assert "query_analyst" not in out  # the node name only appears in the breakdown


def test_main_no_usage_lines_reports_empty(tmp_path, capsys) -> None:
    """A log with no usage lines prints 'no usage lines found'."""
    log = tmp_path / "empty.log"
    log.write_text("just some output\nno tokens here\n")
    code = main([str(log)])
    out = capsys.readouterr().out
    assert code == 0
    assert "no usage lines found" in out


def test_main_missing_file_warns_but_continues(tmp_path, capsys) -> None:
    """An unreadable file warns to stderr and continues with the rest."""
    good = tmp_path / "good.log"
    good.write_text("[node] usage: input_tokens=10 output_tokens=5 total_tokens=15\n")
    code = main([str(tmp_path / "missing.log"), str(good)])
    captured = capsys.readouterr()
    assert code == 0
    assert "cannot read" in captured.err
    assert "15" in captured.out  # the good file's total still printed