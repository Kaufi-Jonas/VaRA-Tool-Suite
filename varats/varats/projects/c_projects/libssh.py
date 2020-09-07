"""Project file for libssh."""
import typing as tp

import benchbuild as bb
from benchbuild.utils.cmd import make, cmake, mkdir
from benchbuild.utils.settings import get_number_of_jobs
from plumbum import local

from varats.data.provider.cve.cve_provider import CVEProviderHook
from varats.paper.paper_config import project_filter_generator
from varats.utils.project_util import (
    ProjectBinaryWrapper,
    get_all_revisions_between,
    wrap_paths_to_binaries,
    get_local_project_git_path,
    BinaryType,
)
from varats.utils.settings import bb_cfg


class Libssh(bb.Project, CVEProviderHook):  # type: ignore
    """
    SSH library.

    (fetched by Git)
    """

    NAME = 'libssh'
    GROUP = 'c_projects'
    DOMAIN = 'library'

    SOURCE = [
        bb.source.Git(
            remote="https://github.com/libssh/libssh-mirror.git",
            local="libssh",
            refspec="HEAD",
            limit=None,
            shallow=False,
            version_filter=project_filter_generator("libssh")
        )
    ]

    @property
    def binaries(self) -> tp.List[ProjectBinaryWrapper]:
        """Return a list of binaries generated by the project."""
        libssh_git_path = get_local_project_git_path(self.NAME)
        libssh_version = self.version_of_primary
        with local.cwd(libssh_git_path):
            versions_with_src_library_folder = get_all_revisions_between(
                "c65f56aefa50a2e2a78a0e45564526ecc921d74f",
                "9c4baa7fd58b9e4d9cdab4a03d18dd03e0e587ab",
                short=True
            )
            if libssh_version in versions_with_src_library_folder:
                return wrap_paths_to_binaries([
                    ('build/src/libssh.so', BinaryType.shared_library)
                ])

            return wrap_paths_to_binaries([
                ('build/lib/libssh.so', BinaryType.shared_library)
            ])

    def run_tests(self) -> None:
        pass

    def compile(self) -> None:
        """Compile the project."""
        libssh_git_path = get_local_project_git_path(self.NAME)
        libssh_version = self.version_of_primary

        with local.cwd(libssh_git_path):
            cmake_revisions = get_all_revisions_between(
                "0151b6e17041c56813c882a3de6330c82acc8d93",
                "master",
                short=True
            )

        if libssh_version in cmake_revisions:
            self.__compile_cmake()
        else:
            self.__compile_make()

    def __compile_cmake(self) -> None:
        libssh_source = local.path(self.source_of(self.primary_source))

        compiler = bb.compiler.cc(self)  # type: ignore
        mkdir("-p", libssh_source / "build")
        with local.cwd(libssh_source / "build"):
            with local.env(CC=str(compiler)):
                bb.watch(cmake)("-G", "Unix Makefiles", "..")  # type: ignore

            bb.watch(make)("-j", get_number_of_jobs(bb_cfg()))  # type: ignore

    def __compile_make(self) -> None:
        libssh_source = local.path(self.source_of(self.primary_source))

        compiler = bb.compiler.cc(self)  # type: ignore
        with local.cwd(libssh_source):
            with local.env(CC=str(compiler)):
                configure = bb.watch(local["./configure"])  # type: ignore
                configure()
            bb.watch(make)("-j", get_number_of_jobs(bb_cfg()))  # type: ignore

    @classmethod
    def get_cve_product_info(cls) -> tp.List[tp.Tuple[str, str]]:
        return [("Libssh", "Libssh")]
