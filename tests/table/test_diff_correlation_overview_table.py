"""Test the DiffCorrelationOverviewTable class."""
import unittest

from tests.test_utils import run_in_test_environment, UnitTestFixtures
from varats.paper_mgmt.paper_config import load_paper_config
from varats.projects.discover_projects import initialize_projects
from varats.table.tables import TableConfig, TableFormat
from varats.tables import diff_correlation_overview_table
from varats.utils.settings import vara_cfg


class TestDiffCorrelationOverviewTable(unittest.TestCase):
    """Test the DiffCorrelationOverviewTable class."""

    @run_in_test_environment(
        UnitTestFixtures.PAPER_CONFIGS, UnitTestFixtures.RESULT_FILES
    )
    def test_table_tex_output(self) -> None:
        """Check whether the table produces the correct tex output."""
        vara_cfg()["paper_config"]["current_config"
                                  ] = "test_diff_correlation_overview_table"
        initialize_projects()
        load_paper_config()
        table_str = diff_correlation_overview_table.DiffCorrelationOverviewTable(
            TableConfig.from_kwargs(view=False)
        ).tabulate(TableFormat.LATEX_BOOKTABS, False)

        self.assertEqual(
            r"""\begin{tabular}{lrrrr}
\toprule
{} & \multicolumn{4}{c}{xz} \\
{} & {Churn} & {Num Interactions} & {Num Interacting Commits} & {Num Interacting Authors} \\
\midrule
Churn & 1.00 & 1.00 & -1.00 & nan \\
Num Interactions & 1.00 & 1.00 & -1.00 & nan \\
Num Interacting Commits & -1.00 & -1.00 & 1.00 & nan \\
Num Interacting Authors & nan & nan & nan & nan \\
\bottomrule
\end{tabular}
""", table_str
        )
