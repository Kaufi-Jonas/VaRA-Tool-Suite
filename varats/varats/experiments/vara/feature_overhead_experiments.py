"""Module for experiments that measure the runtime overhead introduced by
instrumenting binaries produced by a project."""
import typing as tp
from pathlib import Path
from time import sleep

from benchbuild import Project
from benchbuild.extensions import compiler, run
from benchbuild.extensions import time as bbtime
from benchbuild.utils import actions
from benchbuild.utils.cmd import time
from plumbum import BG, FG, local
from plumbum.commands.modifiers import Future

from varats.data.reports.empty_report import EmptyReport
from varats.experiment.experiment_util import (
    ExperimentHandle,
    ZippedReportFolder,
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
from varats.report.gnu_time_report import TimeReport, TimeReportAggregate
from varats.report.report import FileStatusExtension, ReportSpecification
from varats.report.tef_report import TEFReport, TEFReportAggregate
from varats.tools.research_tools.vara import VaRA


class ExecWithTime(actions.Step):  # type: ignore
    """Executes the specified binaries of the project, in specific
    configurations, against one or multiple workloads and with or without
    feature tracing."""

    NAME = "ExecWithTime"
    DESCRIPTION = "Executes each binary and measures its runtime using `time`."

    def __init__(
        self,
        project: Project,
        experiment_handle: ExperimentHandle,
        num_iterations: int,
        usdt: bool = False
    ):
        super().__init__(obj=project, action_fn=self.run_perf_tracing)
        self.__experiment_handle = experiment_handle
        self.__num_iterations = num_iterations
        self.__usdt = usdt

    def run_perf_tracing(self) -> actions.StepResult:
        """Execute the specified binaries of the project, in specific
        configurations, against one or multiple workloads."""
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

            # Assemble Path for TEF report.
            tef_report_file_name = self.__experiment_handle.get_file_name(
                TEFReportAggregate.shorthand(),
                project_name=project.name,
                binary_name=binary.name,
                project_revision=project.version_of_primary,
                project_uuid=str(project.run_uuid),
                extension_type=FileStatusExtension.SUCCESS
            )

            tef_report_file = Path(
                vara_result_folder, str(tef_report_file_name)
            )

            # Assemble Path for time report.
            time_report_file_name = self.__experiment_handle.get_file_name(
                TimeReportAggregate.shorthand(),
                project_name=project.name,
                binary_name=binary.name,
                project_revision=project.version_of_primary,
                project_uuid=str(project.run_uuid),
                extension_type=FileStatusExtension.SUCCESS
            )

            time_report_file = Path(
                vara_result_folder, str(time_report_file_name)
            )

            # Execute binary.
            with ZippedReportFolder(tef_report_file) as tef_tmp, \
                    ZippedReportFolder(time_report_file) as time_tmp:

                for i in range(self.__num_iterations):

                    # Print progress.
                    print(
                        f"Binary={binary.name} Progress "
                        f"{i}/{self.__num_iterations}",
                        flush=True
                    )

                    # Generate report file names.
                    tef_report_file = Path(
                        tef_tmp, f"tef_iteration_{i}.{TEFReport.FILE_TYPE}"
                    )
                    time_report_file = Path(
                        time_tmp, f"time_iteration_{i}.{TimeReport.FILE_TYPE}"
                    )

                    with local.cwd(project.source_of_primary), \
                            local.env(VARA_TRACE_FILE=tef_report_file):
                        run_cmd = binary[workload]
                        run_cmd = time["-v", "-o", time_report_file, run_cmd]

                        # Attach bcc script to activate USDT probes.
                        bcc_runner: Future
                        if self.__usdt:
                            bcc_script_location = Path(
                                VaRA.install_location(),
                                "tools/perf_bpf_tracing/UsdtTefMarker.py"
                            )
                            bcc_script = local[str(bcc_script_location)]

                            # Assertion: Can be run without sudo password prompt.
                            bcc_cmd = bcc_script["--output_file",
                                                 tef_report_file, "--no_poll",
                                                 "--executable", binary.path]
                            with local.as_root():
                                bcc_runner = bcc_cmd & BG

                            sleep(1)  # give bcc script time to start up

                        # Run.
                        run_cmd & FG

                        # Wait for bcc running in background to exit.
                        if self.__usdt:
                            bcc_runner.wait()

        return actions.StepResult.OK


class FeatureDryTime(VersionExperiment, shorthand="FDT"):
    """Test runner for capturing baseline runtime (without any
    instrumentation)."""

    NAME = "FeatureDryTime"

    REPORT_SPEC = ReportSpecification(
        EmptyReport, TimeReportAggregate, TEFReportAggregate
    )

    # Indicate whether to trace binaries and whether USDT markers should be used
    TRACE_BINARIES = False
    USE_USDT = False

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
        if self.TRACE_BINARIES or self.USE_USDT:
            fm_provider = FeatureModelProvider.create_provider_for_project(
                project
            )
            if fm_provider is None:
                raise Exception("Could not get FeatureModelProvider!")

            fm_path = fm_provider.get_feature_model_path(
                project.version_of_primary
            )
            if fm_path is None or not fm_path.exists():
                raise FeatureModelNotFound(project, fm_path)

            # Sets vara tracing flags
            project.cflags += [
                "-fvara-feature", f"-fvara-fm-path={fm_path.absolute()}",
                "-fsanitize=vara"
            ]
            if self.USE_USDT:
                project.cflags += ["-fvara-instr=usdt"]
            elif self.TRACE_BINARIES:
                project.cflags += ["-fvara-instr=trace_event"]

            project.cflags += ["-flto", "-fuse-ld=lld"]
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

        analysis_actions.append(
            ExecWithTime(
                project, self.get_handle(), 100, self.TRACE_BINARIES and
                self.USE_USDT
            )
        )

        analysis_actions.append(actions.Clean(project))

        return analysis_actions


class FeatureDryTimeUSDT(FeatureDryTime, shorthand="FDTUsdt"):
    """Test runner for capturing baseline runtime with inactive USDT markers."""

    NAME = "FeatureDryTimeUsdt"

    TRACE_BINARIES = False
    USE_USDT = True

    def actions_for_project(
        self, project: Project
    ) -> tp.MutableSequence[actions.Step]:

        return super().actions_for_project(project)


class FeatureTefTime(FeatureDryTime, shorthand="FTT"):
    """Test runner for capturing runtime with TEF markers enabled, which produce
    a Catapult trace file."""

    NAME = "FeatureTefTime"

    TRACE_BINARIES = True
    USE_USDT = False

    def actions_for_project(
        self, project: Project
    ) -> tp.MutableSequence[actions.Step]:

        return super().actions_for_project(project)


class FeatureTefTimeUSDT(FeatureDryTime, shorthand="FTTUsdt"):
    """Test runner for capturing runtime with active USDT markers, which produce
    a Catapult trace file."""

    NAME = "FeatureTefTimeUsdt"

    TRACE_BINARIES = True
    USE_USDT = True

    def actions_for_project(
        self, project: Project
    ) -> tp.MutableSequence[actions.Step]:

        return super().actions_for_project(project)
