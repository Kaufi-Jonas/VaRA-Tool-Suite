"""Generates multiple plot types for `TimeReportAggregate`."""

import typing as tp
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from varats.paper_mgmt.case_study import get_case_study_file_name_filter
from varats.paper_mgmt.paper_config import get_loaded_paper_config
from varats.plot.plot import Plot
from varats.plot.plots import PlotGenerator, PlotConfig
from varats.report.gnu_time_report import TimeReportAggregate
from varats.revision.revisions import get_processed_revisions_files


class TimeBoxPlot(Plot, plot_name="time_boxplot"):
    """Box plot of `TimeReportAggregate`."""

    NAME = 'time_boxplot'

    def __init__(self, plot_config: PlotConfig, **kwargs: tp.Any) -> None:
        super().__init__(plot_config, **kwargs)

    def plot(self, view_mode: bool) -> None:

        case_studies = get_loaded_paper_config().get_all_case_studies()

        plot_values: tp.List[tp.Dict[str, tp.Any]] = []

        for case_study in case_studies:
            project_name = case_study.project_name

            report_files = get_processed_revisions_files(
                project_name, TimeReportAggregate,
                get_case_study_file_name_filter(case_study), False
            )

            for report_file in report_files:

                time_aggregated = TimeReportAggregate(report_file)
                with time_aggregated:

                    for time_report in time_aggregated.reports:

                        plot_values.append({
                            "project":
                                project_name,
                            "time_report_aggregate":
                                Path(report_file).name,
                            "wall_clock_time":
                                time_report.wall_clock_time.total_seconds()
                        })

        if (not plot_values):
            return

        data = pd.DataFrame(plot_values)

        sns.boxplot(x="time_report_aggregate", y="wall_clock_time", data=data)

        sns.stripplot(
            x="time_report_aggregate",
            y="wall_clock_time",
            data=data,
            color=".3"
        )


class TimeBoxPlotGenerator(
    PlotGenerator, generator_name="time-boxplot", options=[]
):
    """Generates a box plot for `TimeReportAggregate`."""

    def generate(self) -> tp.List[Plot]:
        return [TimeBoxPlot(self.plot_config, **self.plot_kwargs)]


class PrintTimeSummary(Plot, plot_name="print_time_summary"):
    """Prints `TimeReportAggregate.summary` to stdout."""

    NAME = 'print_time_summary'

    def __init__(self, plot_config: PlotConfig, **kwargs: tp.Any) -> None:
        super().__init__(plot_config, **kwargs)

    def plot(self, view_mode: bool) -> None:

        case_studies = get_loaded_paper_config().get_all_case_studies()

        for case_study in case_studies:

            report_files = get_processed_revisions_files(
                case_study.project_name, TimeReportAggregate,
                get_case_study_file_name_filter(case_study), False
            )

            for report_file in report_files:

                time_aggregated = TimeReportAggregate(report_file)
                with time_aggregated:

                    print(f"project={Path(report_file).name}")
                    print(time_aggregated.summary)


class PrintTimeSummaryGenerator(
    PlotGenerator, generator_name="print-time-summary", options=[]
):
    """Generator for `PrintTimeSummary`."""

    def generate(self) -> tp.List[Plot]:
        return [PrintTimeSummary(self.plot_config, **self.plot_kwargs)]
