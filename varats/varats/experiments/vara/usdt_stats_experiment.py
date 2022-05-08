"""Module for experiments that measures statistics about the execution of a
binary using VaRA's isntrumented USDT probes."""
import typing as tp
from pathlib import Path
from time import sleep

from benchbuild import Project
from benchbuild.extensions import compiler, run
from benchbuild.extensions import time as bbtime
from benchbuild.utils import actions
from benchbuild.utils.cmd import bpftrace
from plumbum import BG, FG, local
from plumbum.commands.modifiers import Future

from varats.data.reports.empty_report import EmptyReport
from varats.experiment.experiment_util import (
    ExperimentHandle,
    get_varats_result_folder,
    VersionExperiment,
    get_default_compile_error_wrapped,
)
from varats.project.project_util import ProjectBinaryWrapper, BinaryType
from varats.provider.feature.feature_model_provider import (
    FeatureModelProvider,
    FeatureModelNotFound,
)
from varats.provider.workload.workload_provider import WorkloadProvider
from varats.report.report import FileStatusExtension, ReportSpecification
from varats.tools.research_tools.vara import VaRA


class WriteUsdtStats(actions.Step):  # type: ignore
    NAME = "WriteUsdtStats"
    DESCRIPTION = "Executes each binary and collects runtime statistics using VaRA's probes and a bpftrace script."

    def __init__(self, project: Project, experiment_handle: ExperimentHandle):
        super().__init__(obj=project, action_fn=self.run)
        self.__experiment_handle = experiment_handle

    def run(self) -> actions.StepResult:
        project: Project = self.obj

        vara_result_folder = get_varats_result_folder(project)
        binary: ProjectBinaryWrapper

        for binary in project.binaries:
            if binary.type != BinaryType.EXECUTABLE:
                continue

            # Get workload to use.
            workload_provider = WorkloadProvider.create_provider_for_project(
                project
            )
            workload = workload_provider.get_workload_for_binary(binary.name)
            if (workload == None):
                print(
                    f"No workload for project={project.name} binary={binary.name}. Skipping."
                )
                continue

            # Assemble Path for report.
            report_file_name = self.__experiment_handle.get_file_name(
                EmptyReport.shorthand(),
                project_name=project.name,
                binary_name=binary.name,
                project_revision=project.version_of_primary,
                project_uuid=str(project.run_uuid),
                extension_type=FileStatusExtension.SUCCESS
            )

            report_file = Path(vara_result_folder, str(report_file_name))

            # Execute binary.
            with local.cwd(project.source_of_primary):
                run_cmd = binary[workload]

                # attach bpftrace to binary to allow tracing it via USDT
                bpftrace_script = Path(
                    VaRA.install_location(),
                    "tools/perf_bpf_tracing/UsdtExecutionStats.bt"
                )

                # Assertion: Can be run without sudo password prompt.
                bpftrace_cmd = bpftrace["-o", report_file, bpftrace_script,
                                        binary.path]

                bpftrace_runner: Future
                with local.as_root():
                    bpftrace_runner = bpftrace_cmd & BG

                sleep(1)  # give bpftrace time to start up

                # Run.
                run_cmd & FG

                # Wait for bpftrace running in background to exit.
                bpftrace_runner.wait()

        return actions.StepResult.OK


class UsdtExecStats(VersionExperiment, shorthand="VUS"):
    """Runner for capturing execution statistics using VaRA's USDT based
    instrumentation."""

    NAME = "UsdtStats"

    REPORT_SPEC = ReportSpecification(EmptyReport)

    def actions_for_project(
        self, project: Project
    ) -> tp.MutableSequence[actions.Step]:
        """
        Returns the specified steps to run the project(s) specified in the call
        in a fixed order.

        Args:
            project: to analyze
        """

        # Add tracing markers.
        fm_provider = FeatureModelProvider.create_provider_for_project(project)
        if fm_provider is None:
            raise Exception("Could not get FeatureModelProvider!")

        fm_path = fm_provider.get_feature_model_path(project.version_of_primary)

        if fm_path is None or not fm_path.exists():
            raise FeatureModelNotFound(project, fm_path)

        # Sets vara tracing flags
        project.cflags += [
            "-fvara-feature", f"-fvara-fm-path={fm_path.absolute()}",
            "-fsanitize=vara", "-fvara-instr=usdt", "-flto", "-fuse-ld=lld"
        ]

        project.ldflags += ["-flto"]

        # Add the required runtime extensions to the project(s).
        project.runtime_extension = run.RuntimeExtension(project, self) \
            << bbtime.RunWithTime()

        # Add the required compiler extensions to the project(s).
        project.compiler_extension = compiler.RunCompiler(project, self) \
            << run.WithTimeout()

        # Add own error handler to compile step.
        project.compile = get_default_compile_error_wrapped(
            self.get_handle(), project, EmptyReport
        )

        analysis_actions = []
        analysis_actions.append(actions.Compile(project))

        analysis_actions.append(WriteUsdtStats(project, self.get_handle()))

        analysis_actions.append(actions.Clean(project))

        return analysis_actions
