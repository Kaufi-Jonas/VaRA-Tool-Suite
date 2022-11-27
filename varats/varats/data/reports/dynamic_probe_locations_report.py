"""Module for DynamicProbeLocationsReport."""

from varats.report.report import BaseReport


class DynamicProbeLocationsReport(
    BaseReport, shorthand="DPL", file_type="json"
):
    """Contains the output of VaRA's BPF script DynamicProbeLocations.bt."""
