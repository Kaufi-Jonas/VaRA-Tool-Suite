"""Base table module."""

import abc
import logging
import typing as tp
from enum import Enum
from pathlib import Path

from pylatex import Document, Package, NoEscape, UnsafeCommand

from varats.paper.case_study import CaseStudy
from varats.table.tables import TableRegistry

LOG = logging.getLogger(__name__)


class TableDataEmpty(Exception):
    """Throw if there was no input data for the table."""


class TableFormat(Enum):
    """List of supported TableFormats."""
    value: str  # pylint: disable=invalid-name

    PLAIN = "plain"
    SIMPLE = "simple"
    GITHUB = "github"
    GRID = "grid"
    FANCY_GRID = "fancy_grid"
    PIPE = "pipe"
    ORGTBL = "orgtbl"
    JIRA = "jira"
    PRESTO = "presto"
    PRETTY = "pretty"
    PSQL = "psql"
    RST = "rst"
    MEDIAWIKI = "mediawiki"
    MOINMOIN = "moinmoin"
    YOUTRACK = "youtrack"
    HTML = "html"
    UNSAFEHTML = "unsafehtml"
    LATEX = "latex"
    LATEX_RAW = "latex_raw"
    LATEX_BOOKTABS = "latex_booktabs"
    TEXTILE = "textile"


class Table(metaclass=TableRegistry):
    """An abstract base class for all tables generated by VaRA-TS."""

    format_filetypes = {
        TableFormat.GITHUB: "md",
        TableFormat.HTML: "html",
        TableFormat.UNSAFEHTML: "html",
        TableFormat.LATEX: "tex",
        TableFormat.LATEX_RAW: "tex",
        TableFormat.LATEX_BOOKTABS: "tex",
        TableFormat.RST: "rst",
    }

    def __init__(self, name: str, **kwargs: tp.Any) -> None:
        self.__name = name
        self.__format = TableFormat.LATEX_BOOKTABS
        self.__saved_extra_args = kwargs

    @property
    def name(self) -> str:
        """
        Name of the current table.

        Test:
        >>> Table('test').name
        'test'
        """
        return self.__name

    @property
    def format(self) -> TableFormat:
        """
        Current table format as used by python-tabulate.

        Test:
        >>> Table('test').format
        <TableFormat.LATEX_BOOKTABS: 'latex_booktabs'>
        """
        return self.__format

    @format.setter
    def format(self, new_format: TableFormat) -> None:
        """
        Set current format of the table.

        Args:
            new_format: a table format as used by python-tabulate
        """
        self.__format = new_format

    @property
    def table_kwargs(self) -> tp.Any:
        """
        Access the kwargs passed to the initial table.

        Test:
        >>> tab = Table('test', foo='bar', baz='bazzer')
        >>> tab.table_kwargs['foo']
        'bar'
        >>> tab.table_kwargs['baz']
        'bazzer'
        """
        return self.__saved_extra_args

    @staticmethod
    def supports_stage_separation() -> bool:
        """True, if the table supports stage separation, i.e., the table can be
        drawn separating the different stages in a case study."""
        return False

    @abc.abstractmethod
    def tabulate(self) -> str:
        """Build the table using tabulate."""

    def table_file_name(self, include_filetype: bool = True) -> str:
        """
        Get the file name this table; will be stored to when calling save.

        Args:
            include_filetype: flags whether to include the file extension at the
                              end of the filename.

        Returns:
            the file name the table will be stored to

        Test:
        >>> p = Table('test', project='bar')
        >>> p.table_file_name()
        'bar_test.tex'
        >>> p = Table('foo', project='bar', table_case_study=CaseStudy('baz',\
                                                                       42))
        >>> p.format = TableFormat.FANCY_GRID
        >>> p.table_file_name()
        'baz_42_foo.txt'
        """
        filetype = self.format_filetypes.get(self.__format, "txt")
        table_ident = ''
        if self.table_kwargs.get('table_case_study', None):
            case_study: CaseStudy = self.table_kwargs['table_case_study']
            table_ident = f"{case_study.project_name}_{case_study.version}_"
        elif 'project' in self.table_kwargs:
            table_ident = f"{self.table_kwargs['project']}_"

        sep_stages = ''
        if self.supports_stage_separation(
        ) and self.table_kwargs.get('sep_stages', None):
            sep_stages = 'S'

        table_file_name = f"{table_ident}{self.name}{sep_stages}"
        if include_filetype:
            table_file_name += f".{filetype}"
        return table_file_name

    @abc.abstractmethod
    def wrap_table(self, table: str) -> str:
        """
        Used to wrap tables inside a complete latex document by passing desired
        parameters to wrap_table_in_document.

        Returns:
            The resulting table string.
        """

    def save(
        self,
        path: tp.Optional[Path] = None,
        wrap_document: bool = False
    ) -> None:
        """
        Save the current table to a file.

        Args:
            path: The path where the file is stored (excluding the file name).
            wrap_document: flags whether to wrap the (latex) table code into a
                           complete document.
        """
        try:
            table = self.tabulate()
        except TableDataEmpty:
            LOG.warning(f"No data for project {self.table_kwargs['project']}.")
            return

        if wrap_document:
            table = self.wrap_table(table)

        if path is None:
            table_dir = Path(self.table_kwargs["table_dir"])
        else:
            table_dir = path

        with open(table_dir / self.table_file_name(), "w") as outfile:
            outfile.write(table)


def wrap_table_in_document(
    table: str, landscape: bool = False, margin: float = 1.5
) -> str:
    """
    Wraps given table inside a proper latex document. Uses longtable instead of
    tabular to fit data on multiple pages.

    Args:
        table: table string to wrap the document around.
        landscape: orientation of the table document. True for landscape mode,
                   i.e. horizontal orientation.
        margin: margin of the wrapped table inside the resulting document.

    Returns:
        string representation of the resulting latex document.
    """
    doc = Document(
        documentclass="scrbook",
        document_options="paper=a4",
        geometry_options={
            "margin": f"{margin}cm",
            "landscape": "true" if landscape else "false"
        }
    )
    # set monospace font
    monospace_comm = UnsafeCommand(
        'renewcommand', r'\familydefault', extra_arguments=r'\ttdefault'
    )
    doc.preamble.append(monospace_comm)

    # package in case longtables are used
    doc.packages.append(Package('longtable'))
    # package for booktabs automatically generated by pandas.to_latex()
    doc.packages.append(Package('booktabs'))

    doc.change_document_style("empty")

    # embed latex table inside document
    doc.append(NoEscape(table))

    # dump function returns string representation of document
    return tp.cast(str, doc.dumps())
