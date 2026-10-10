"""What happens when a command's output is far bigger than a text widget.

The interface has two independent bounds and both are measured here against the real
binary: :class:`SeqkitRunner` stops *previewing* once it has emitted the configured
number of lines but keeps writing every byte to the temporary result file, and each
view in the output panel is a ``QPlainTextEdit`` whose document is capped by
``setMaximumBlockCount``. A 100 000-record FASTA is used because that is what a real
``seqkit`` run over a sequencing file produces, and because the whole case stays inside
a few seconds -- the elapsed time is printed rather than asserted as a bound this
machine could not guarantee.
"""

import time
from pathlib import Path

import pytest

from seqkit_gui.core.builder import RunRequest, build_argv
from seqkit_gui.core.runner import SeqkitRunner
from seqkit_gui.core.spec import load
from seqkit_gui.ui.output_view import MAX_BLOCKS

RECORDS = 100_000
PREVIEW_LIMIT = 5_000
#: One record per line of header plus one line of sequence: what ``seq`` writes for
#: an unwrapped FASTA of ``RECORDS`` records.
EXPECTED_LINES = 2 * RECORDS


@pytest.fixture(scope="module")
def many_records(tmp_path_factory) -> Path:
    """A FASTA of ``RECORDS`` records, built by the shared helper."""
    from conftest import write_records

    path = tmp_path_factory.mktemp("scale") / "many.fa"
    started = time.monotonic()
    write_records(path, RECORDS, length=60)
    print(f"\nbuilt {RECORDS} records in {time.monotonic() - started:.2f}s "
          f"({path.stat().st_size / 1e6:.1f} MB)")
    return path


def run_to_end(runner, program, argv, working_dir, label, timeout=180.0):
    """Drive ``runner`` to its ``finished`` signal without a nested event loop."""
    from PySide6.QtCore import QCoreApplication

    outcome = []
    runner.finished.connect(outcome.append)
    started = time.monotonic()
    runner.start(program, argv, working_dir, label)
    deadline = started + timeout
    while time.monotonic() < deadline and not outcome:
        QCoreApplication.processEvents()
        time.sleep(0.01)
    QCoreApplication.processEvents()
    if not outcome:
        pytest.fail(f"{label} did not finish within {timeout:.0f}s")
    return outcome[0], time.monotonic() - started


def test_a_hundred_thousand_line_result_is_previewed_not_absorbed(qapp, seqkit_binary,
                                                                 many_records):
    """Every line reaches the file; only the configured number reaches the widget."""
    runner = SeqkitRunner(PREVIEW_LIMIT)
    previewed = []
    runner.stdout_chunk.connect(lambda text: previewed.append(text))

    request = RunRequest(command=load().get("seq"), inputs=(str(many_records),))
    result, elapsed = run_to_end(runner, str(seqkit_binary), build_argv(request),
                                 str(many_records.parent), "seq")

    assert result.succeeded, result
    assert result.stdout_bytes > 1_000_000, "the child produced nothing to truncate"
    assert result.truncated and result.dropped_lines > 0
    # The preview holds to exactly the limit; what it gave up is counted per chunk, and
    # a chunk that ends in the middle of a line is charged as one more dropped line, so
    # the counter sits a hair above the arithmetic. The range is the contract: nothing
    # close to the whole output reached the widget, and nothing close to it was lost.
    unshown = EXPECTED_LINES - PREVIEW_LIMIT
    assert unshown <= result.dropped_lines <= unshown + 5, (
        f"{result.dropped_lines} dropped + {PREVIEW_LIMIT} previewed != "
        f"{EXPECTED_LINES} lines")
    assert sum(chunk.count("\n") for chunk in previewed) == PREVIEW_LIMIT, (
        "the preview handed the widget more lines than the limit")

    written = result.stdout_file.read_text(encoding="utf-8", errors="replace")
    assert written.count("\n") == EXPECTED_LINES, "the saved result lost records"
    assert len("".join(previewed)) < result.stdout_bytes, (
        "the widget received more characters than the child produced")

    print(f"\n{RECORDS} records -> {EXPECTED_LINES} output lines, preview held to "
          f"{PREVIEW_LIMIT}, {result.stdout_bytes / 1e6:.1f} MB tee-d to the result "
          f"file, {elapsed:.2f}s total")
    assert elapsed < 60, f"a run that should take seconds took {elapsed:.1f}s"


def test_the_truncation_is_announced_where_the_user_reads_it(qapp, root, seqkit_binary,
                                                             many_records):
    """The panel has to say the preview is partial, not just stop mid-stream."""
    from seqkit_gui.ui.i18n import Catalog
    from seqkit_gui.ui.output_view import OutputPanel

    catalog = Catalog("en_US", directory=root / "seqkit_gui" / "i18n")
    panel = OutputPanel(catalog)
    runner = SeqkitRunner(PREVIEW_LIMIT)
    runner.stdout_chunk.connect(panel.append_stdout)

    request = RunRequest(command=load().get("seq"), inputs=(str(many_records),))
    panel.begin_run("seqkit seq -- many.fa", str(many_records.parent))
    result, _elapsed = run_to_end(runner, str(seqkit_binary), build_argv(request),
                                  str(many_records.parent), "seq")
    panel.end_run(result)

    note = catalog.tr("Output preview truncated, the full result is in the saved file")
    text = panel.result_view.toPlainText()
    assert note in text, "a truncated preview has to say so in the result view"
    assert note in panel.log_view.toPlainText()
    assert panel.result_view.blockCount() <= MAX_BLOCKS + 4
    panel.deleteLater()
    runner.deleteLater()


def test_the_views_are_internally_capped_as_well(qapp, root):
    """``setMaximumBlockCount`` is the second bound.

    Even a writer that ignored the line limit cannot make the document grow without
    bound: the widget drops its own oldest blocks, which is what keeps a 100 000-line
    result from becoming a 100 000-block layout.
    """
    from seqkit_gui.ui.i18n import Catalog
    from seqkit_gui.ui.output_view import OutputPanel

    catalog = Catalog("en_US", directory=root / "seqkit_gui" / "i18n")
    panel = OutputPanel(catalog)
    try:
        for view in (panel.result_view, panel.error_view, panel.log_view):
            assert view.maximumBlockCount() == MAX_BLOCKS
        panel.append_stdout("\n".join(f"line{index}" for index in range(MAX_BLOCKS * 2)))
        assert panel.result_view.blockCount() <= MAX_BLOCKS, (
            f"the document grew to {panel.result_view.blockCount()} blocks")
    finally:
        panel.deleteLater()


def test_the_preview_floor_protects_the_interface_from_an_unusable_limit(qapp):
    """Settings accepts a number; the runner refuses one that would show nothing."""
    runner = SeqkitRunner(1)
    assert runner._limit == 200, runner._limit
    runner.set_preview_limit(50)
    assert runner._limit == 200
    runner.set_preview_limit(40_000)
    assert runner._limit == 40_000
    runner.deleteLater()


def test_the_window_passes_the_configured_limit_to_the_runner(qapp, root, fresh_settings):
    """The preference and the runner must not be two different numbers."""
    from seqkit_gui.core import settings as store
    from seqkit_gui.ui.i18n import Catalog
    from seqkit_gui.ui.main_window import MainWindow

    prefs = store.Preferences(output_line_limit=700)
    window = MainWindow(Catalog("en_US", directory=root / "seqkit_gui" / "i18n"),
                        prefs, load())
    try:
        assert window.runner._limit == 700
        window.prefs.output_line_limit = 9_000
        window.runner.set_preview_limit(window.prefs.output_line_limit)
        assert window.runner._limit == 9_000
    finally:
        window.deleteLater()
