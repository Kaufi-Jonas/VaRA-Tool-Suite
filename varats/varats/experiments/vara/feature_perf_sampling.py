"""Contains feature performance sampling experiments."""
import typing as tp
from pathlib import Path
from time import sleep

from benchbuild import Project
from benchbuild.utils import actions
from benchbuild.utils.cmd import cp, mkdir, numactl, perf, bpftrace, time, sudo
from plumbum import local, BG
from plumbum.commands.modifiers import Future

from varats.data.reports.dynamic_probe_locations_report import (
    DynamicProbeLocationsReport,
)
from varats.data.reports.perf_profile_report import (
    PerfProfileReport,
    PerfProfileReportAggregate,
)
from varats.experiment.experiment_util import (
    ExperimentHandle,
    ZippedReportFolder,
    get_varats_result_folder,
)
from varats.experiment.feature_perf_experiments import (
    FeaturePerfExperiment,
    InstrumentationType,
)
from varats.project.project_util import ProjectBinaryWrapper, BinaryType
from varats.provider.workload.workload_provider import WorkloadProvider
from varats.report.gnu_time_report import TimeReport, TimeReportAggregate
from varats.report.report import FileStatusExtension, ReportSpecification
from varats.tools.research_tools.vara import VaRA


class SampleWithPerf(actions.Step):  # type: ignore
    """See `DESCRIPTION`."""

    NAME = "ProfileWithPerf"
    DESCRIPTION = """TODO"""

    def __init__(
        self, project: Project, experiment_handle: ExperimentHandle,
        sampling_rate: int
    ):
        super().__init__(obj=project, action_fn=self.run)
        self._experiment_handle = experiment_handle
        self._num_iterations = 10
        self._sampling_rate = sampling_rate

    def run(self) -> actions.StepResult:
        """Action function for this step."""
        project: Project = self.obj

        vara_result_folder = get_varats_result_folder(project)

        binary: ProjectBinaryWrapper
        for binary in project.binaries:
            if binary.type != BinaryType.EXECUTABLE:
                continue

            # Copy binary to allow further investigation after experiment.
            binaries_dir = vara_result_folder / "compiled_binaries"
            mkdir("-p", binaries_dir)
            cp(
                Path(project.source_of_primary, binary.path), binaries_dir /
                (f"{binary.name}_" + self._experiment_handle.shorthand())
            )

            # Get workload to use.
            # pylint: disable=W0511
            # TODO (se-sic/VaRA#841): refactor to bb workloads if possible
            workload_provider = WorkloadProvider.create_provider_for_project(
                project
            )
            if not workload_provider:
                print(
                    f"No workload provider for project={project.name}. " \
                    "Skipping."
                )
                return actions.StepResult.CAN_CONTINUE
            workload = workload_provider.get_workload_for_binary(binary.name)
            if workload is None:
                print(
                    f"No workload for project={project.name} " \
                        f"binary={binary.name}. Skipping."
                )
                continue

            # collect dynamic probe locations
            dpl_report_name = self._experiment_handle.get_file_name(
                DynamicProbeLocationsReport.shorthand(),
                project_name=project.name,
                binary_name=binary.name,
                project_revision=project.version_of_primary,
                project_uuid=str(project.run_uuid),
                extension_type=FileStatusExtension.SUCCESS
            )

            dpl_report_file = Path(vara_result_folder, str(dpl_report_name))

            with local.cwd(project.source_of_primary):
                bpf_script: Future = self.attach_dynamic_probe_locations_bpf_script(
                    dpl_report_file, binary.path
                )
                binary(workload)
                bpf_script.wait()

            # report files
            perf_report_zip_name = self._experiment_handle.get_file_name(
                PerfProfileReportAggregate.shorthand(),
                project_name=project.name,
                binary_name=binary.name,
                project_revision=project.version_of_primary,
                project_uuid=str(project.run_uuid),
                extension_type=FileStatusExtension.SUCCESS
            )
            perf_report_zip = Path(
                vara_result_folder, str(perf_report_zip_name)
            )

            # Assemble Path for time report.
            time_report_zip_name = self._experiment_handle.get_file_name(
                TimeReportAggregate.shorthand(),
                project_name=project.name,
                binary_name=binary.name,
                project_revision=project.version_of_primary,
                project_uuid=str(project.run_uuid),
                extension_type=FileStatusExtension.SUCCESS,
            )

            time_report_zip = Path(
                vara_result_folder, str(time_report_zip_name)
            )

            with ZippedReportFolder(time_report_zip) as time_tmp, \
                ZippedReportFolder(perf_report_zip) as perf_tmp:
                for i in range(self._num_iterations):

                    # Execute and trace binary.
                    # Print progress.
                    print(
                        f"Binary={binary.name} Progress "
                        f"{i}/{self._num_iterations}",
                        flush=True
                    )

                    # Generate full report filenames.
                    time_report_file = Path(
                        time_tmp, f"iteration_{i}.{TimeReport.FILE_TYPE}"
                    )
                    perf_report_file = Path(
                        perf_tmp, f"iteration_{i}.{PerfProfileReport.FILE_TYPE}"
                    )

                    with local.cwd(project.source_of_primary):
                        run_cmd = binary[workload]
                        run_cmd = time["-v", "-o", time_report_file, run_cmd]
                        run_cmd = perf["record", "-F", self._sampling_rate,
                                       "-g", "--user-callchains", "-o",
                                       perf_report_file, run_cmd]
                        run_cmd = numactl["--cpunodebind=0", "--membind=0",
                                          run_cmd]
                        run_cmd()
        return actions.StepResult.OK

    @staticmethod
    def attach_dynamic_probe_locations_bpf_script(
        report_file: Path, binary: Path
    ) -> Future:
        """Attach bpftrace script to binary to activate USDT probes."""
        bpftrace_script_location = Path(
            VaRA.install_location(),
            "share/vara/perf_bpf_tracing/DynamicProbeLocations.bt"
        )
        bpftrace_script = bpftrace["-o", report_file, bpftrace_script_location,
                                   binary]
        bpftrace_script.with_env(BPFTRACE_PERF_RB_PAGES=512)

        # Assertion: Can be run without sudo password prompt.
        bpftrace_cmd = sudo[bpftrace_script]

        bpftrace_runner = bpftrace_cmd & BG
        sleep(10)  # give bpftrace time to start up
        return bpftrace_runner


class FeaturePerfSampling97Hz(FeaturePerfExperiment, shorthand="FPS97Hz"):
    """"""

    NAME = "FeaturePerfSampling97Hz"
    REPORT_SPEC = ReportSpecification(
        TimeReportAggregate, PerfProfileReportAggregate,
        DynamicProbeLocationsReport
    )

    def actions_for_project(
        self,
        project: Project,
        instrumentation: InstrumentationType = InstrumentationType.USDT_RAW,
        analysis_actions: tp.Optional[tp.Iterable[actions.Step]] = None,
        use_feature_model: bool = True,
        sampling_rate: int = 97
    ) -> tp.MutableSequence[actions.Step]:

        analysis_actions = [
            SampleWithPerf(project, self.get_handle(), sampling_rate)
        ]
        actions = super().actions_for_project(
            project, instrumentation, analysis_actions, use_feature_model
        )
        return actions


class FeaturePerfSampling997Hz(FeaturePerfSampling97Hz, shorthand="FPS997Hz"):
    """"""

    NAME = "FeaturePerfSampling997Hz"

    def actions_for_project(
        self, project: Project
    ) -> tp.MutableSequence[actions.Step]:
        return super().actions_for_project(project, sampling_rate=997)
