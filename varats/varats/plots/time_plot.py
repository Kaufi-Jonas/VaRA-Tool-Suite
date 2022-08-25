"""Generates multiple plot types for `TimeReportAggregate`."""

import typing as tp

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from varats.paper_mgmt.case_study import get_case_study_file_name_filter
from varats.paper_mgmt.paper_config import get_loaded_paper_config
from varats.plot.plot import Plot
from varats.plot.plots import PlotGenerator, PlotConfig
from varats.report.gnu_time_report import TimeReportAggregate
from varats.revision.revisions import get_processed_revisions_files

_experiment_short_subsitution = {
    "FPA_Dry": "Dry",
    "FPA_Dry_USDT": "Inactive USDT",
    "FPA_TEF": "TEF Baseline",
    "FPA_TEF_USDT": "TEF USDT"
}


class TimeBoxPlot(Plot, plot_name="time_boxplot"):
    """Box plot of `TimeReportAggregate`."""

    NAME = 'time_boxplot'

    def __init__(self, plot_config: PlotConfig, **kwargs: tp.Any) -> None:
        super().__init__(plot_config, **kwargs)

    def plot(self, view_mode: bool) -> None:

        case_studies = get_loaded_paper_config().get_all_case_studies()
        df = pd.DataFrame()
        binaries: tp.Set[str] = set()

        for case_study in case_studies:
            project_name = case_study.project_name

            report_files = get_processed_revisions_files(
                project_name, TimeReportAggregate,
                get_case_study_file_name_filter(case_study), False
            )

            for report_file in report_files:

                time_aggregated = TimeReportAggregate(report_file)
                report_name = time_aggregated.filename

                binaries.add(report_name.binary_name)

                for measurement in time_aggregated.measurements_wall_clock_time:
                    new_row = {
                        "binary":
                            report_name.binary_name,
                        "experiment":
                            _experiment_short_subsitution.get(
                                report_name.experiment_shorthand,
                                report_name.experiment_shorthand
                            ),
                        "runtime":
                            measurement
                    }

                    df = df.append(new_row, ignore_index=True)

        df.sort_values(["binary", "experiment"], inplace=True)

        for binary in binaries:
            plt.figure(binary)
            data = df[(df["binary"] == binary)]

            # Show each observation with a scatterplot
            sns.stripplot(
                x="experiment",
                y="runtime",
                data=data,
                dodge=True,
                alpha=.4,
                zorder=1
            )

            # Show means and standard deviation
            sns.pointplot(
                x="experiment",
                y="runtime",
                data=data,
                join=False,
                palette="dark",
                markers="d",
                ci="sd"
            )
            plt.ylabel("Runtime in Seconds")
            plt.xlabel(None)


class TimeBoxPlotGenerator(
    PlotGenerator, generator_name="time-boxplot", options=[]
):
    """Generates a box plot for `TimeReportAggregate`."""

    def generate(self) -> tp.List[Plot]:
        return [TimeBoxPlot(self.plot_config, **self.plot_kwargs)]
