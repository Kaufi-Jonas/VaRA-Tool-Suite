"""Report for the 'perf stat' command."""

from varats.report.report import BaseReport


class PerfStatReport(BaseReport, shorthand="PERF", file_type="txt"):
    """
    An empty report for testing.

    Nothing gets printed into the report and the result file has no file type.
    """
