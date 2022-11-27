"""Module for a perf profile report."""

from varats.report.report import BaseReport


class PerfProfileReport(BaseReport, shorthand="PERF", file_type="data"):
    """
    Binary `perf.data` file created by `perf record`.

    Can be converted into human-readable format via `perf data convert --to-json
    <out_filename>`.
    """
