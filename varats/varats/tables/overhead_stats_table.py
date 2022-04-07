"""Module for overhead measurement statistics tables."""
import typing as tp

import pandas as pd
from tabulate import tabulate

from varats.paper_mgmt.case_study import get_case_study_file_name_filter
from varats.paper_mgmt.paper_config import get_loaded_paper_config
from varats.report.gnu_time_report import TimeReportAggregate
from varats.revision.revisions import get_processed_revisions_files
from varats.table.table import Table, wrap_table_in_document
from varats.table.tables import TableFormat


class FeatureOverheadStats(Table):
    """Table comparing statistics of overhead measurements on the same
    binaries."""

    NAME = "time_stats"

    def __init__(self, **kwargs: tp.Any):
        super().__init__(self.NAME, **kwargs)

    def tabulate(self) -> str:
        case_studies = get_loaded_paper_config().get_all_case_studies()

        cs_data: tp.List[pd.DataFrame] = []
        for case_study in case_studies:
            project_name = case_study.project_name

            report_files = get_processed_revisions_files(
                project_name, TimeReportAggregate,
                get_case_study_file_name_filter(case_study), False
            )

            for report_file in report_files:

                time_aggregated = TimeReportAggregate(report_file)
                with time_aggregated:

                    report_name = time_aggregated.filename
                    cs_dict = {
                        report_name.binary_name: {
                            "Experiment": report_name.experiment_shorthand,
                            "Commit": report_name.commit_hash,
                            "Mean": time_aggregated.mean_wall_clock_time,
                            "Std": time_aggregated.std_wall_clock_time,
                            "Min": time_aggregated.wall_clock_time_min,
                            "Max": time_aggregated.wall_clock_time_max,
                        }
                    }

                    cs_data.append(
                        pd.DataFrame.from_dict(cs_dict, orient="index")
                    )

        df = pd.concat(cs_data).sort_values("Experiment").sort_index()

        if self.format in [
            TableFormat.LATEX, TableFormat.LATEX_BOOKTABS, TableFormat.LATEX_RAW
        ]:
            table = df.to_latex(
                bold_rows=True, multicolumn_format="c", multirow=True
            )
            return str(table) if table else ""
        return tabulate(df, df.columns, self.format.value)

    def wrap_table(self, table: str) -> str:
        return wrap_table_in_document(table=table, landscape=True)
