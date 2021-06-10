"""Implements the SZZUnleashed experiment."""

import typing as tp

import yaml
from benchbuild import Experiment, Project, source
from benchbuild.experiment import ProjectT
from benchbuild.utils import actions
from benchbuild.utils.cmd import mkdir
from pygit2 import Commit

from varats.base.version_header import VersionHeader
from varats.data.reports.szz_report import (
    SZZReport,
    PyDrillerSZZReport,
    SZZTool,
)
from varats.provider.bug.bug_provider import BugProvider
from varats.report.report import FileStatusExtension as FSE
from varats.utils.settings import bb_cfg


class CreatePyDrillerSZZReport(actions.Step):  # type: ignore
    """
    Create a SZZReport from the data collected by the.

    :class:`~varats.provider.bug.bug_provider.BugProvider`.
    """
    NAME = "CreatePyDrillerSZZReport"
    DESCRIPTION = "Create a report from SZZ data"

    RESULT_FOLDER_TEMPLATE = "{result_dir}/{project_dir}"

    def __init__(self, project: Project):
        super().__init__(obj=project, action_fn=self.create_report)

    def create_report(self) -> actions.StepResult:
        """Create a report from SZZ data."""
        project = self.obj

        bug_provider = BugProvider.get_provider_for_project(project)
        pygit_bugs = bug_provider.find_all_pygit_bugs()

        varats_result_folder = self.RESULT_FOLDER_TEMPLATE.format(
            result_dir=str(bb_cfg()["varats"]["outfile"]),
            project_dir=str(project.name)
        )
        mkdir("-p", varats_result_folder)

        def commit_to_hash(commit: Commit) -> str:
            return str(commit.id)

        bugs: tp.Dict[str, tp.List[str]] = {}
        # entries are lists of the form [<fix>, <introducing>]
        for bug in pygit_bugs:
            bugs[commit_to_hash(bug.fixing_commit)] = sorted([
                commit_to_hash(commit) for commit in bug.introducing_commits
            ])
        raw_szz_report = {
            "szz_tool": SZZTool.PYDRILLER_SZZ.tool_name,
            "bugs": bugs
        }

        result_file = PyDrillerSZZReport.get_file_name(
            project_name=str(project.name),
            binary_name="none",  # we don't rely on binaries in this experiment
            project_version=project.version_of_primary,
            project_uuid=str(project.run_uuid),
            extension_type=FSE.Success
        )

        with open(f"{varats_result_folder}/{result_file}", "w") as yaml_file:
            yaml_file.write(
                yaml.dump_all([
                    VersionHeader.from_version_number("SZZReport",
                                                      1).get_dict(),
                    raw_szz_report
                ],
                              explicit_start=True,
                              explicit_end=True)
            )

        return actions.StepResult.OK


class PyDrillerSZZExperiment(Experiment):  # type: ignore
    """
    Generates a PyDrillerSZZ report.

    This experiment should be run only on one (preferably the newest) revision
    of a project.
    """

    NAME = "PyDrillerSZZ"

    REPORT_TYPE = SZZReport

    @classmethod
    def sample(cls, prj_cls: ProjectT) -> tp.List[source.VariantContext]:
        variants = list(source.product(*prj_cls.SOURCE))
        return [source.context(*variants[0])]

    def actions_for_project(self, project: Project) -> tp.List[actions.Step]:
        """Returns the specified steps to run the project(s) specified in the
        call in a fixed order."""

        analysis_actions = [
            CreatePyDrillerSZZReport(project),
            actions.Clean(project)
        ]

        return analysis_actions
