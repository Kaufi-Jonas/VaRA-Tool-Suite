"""Test VaRA project utilities."""
import typing as tp
import unittest
from os.path import isdir
from pathlib import Path

from benchbuild.utils.cmd import git, mkdir
from plumbum import local

from tests.test_utils import run_in_test_environment, UnitTestFixtures
from varats.project.project_util import (
    get_project_cls_by_name,
    get_loaded_vara_projects,
    ProjectBinaryWrapper,
    BinaryType,
)
from varats.projects.c_projects.gravity import Gravity
from varats.projects.discover_projects import initialize_projects
from varats.tools.bb_config import create_new_bb_config
from varats.ts_utils.project_sources import (
    VaraTestRepoSource,
    VaraTestRepoSubmodule,
)
from varats.utils.settings import create_new_varats_config, bb_cfg


class TestProjectLookup(unittest.TestCase):
    """Tests different project lookup methods."""

    @classmethod
    def setUp(cls) -> None:
        """Initialize all projects before running tests."""
        initialize_projects()

    def test_project_lookup_by_name(self) -> None:
        """Check if we can load project classes from their name."""
        grav_prj_cls = get_project_cls_by_name("gravity")

        self.assertEqual(grav_prj_cls, Gravity)

    def test_failed_project_lookup(self) -> None:
        """Check if we correctly fail, should a project be queried that does not
        exist."""
        self.assertRaises(
            LookupError, get_project_cls_by_name, "this_project_does_not_exists"
        )

    def test_project_iteration(self) -> None:
        """Check if we can iterate over loaded vara projects."""
        found_gravity = False
        for prj_cls in get_loaded_vara_projects():
            if prj_cls.NAME == "gravity":
                found_gravity = True

        self.assertTrue(found_gravity)


class TestVaraTestRepoSource(unittest.TestCase):
    """Test if directories and files of a VaraTestRepoSource and its
    VaraTestRepoSubmodules are correctly set up."""

    revision: tp.ClassVar[str]
    bb_result_report_path: tp.ClassVar[Path]
    bb_result_lib_path: tp.ClassVar[Path]
    elementalist: tp.ClassVar[VaraTestRepoSource]
    fire_lib: tp.ClassVar[VaraTestRepoSubmodule]
    water_lib: tp.ClassVar[VaraTestRepoSubmodule]

    @classmethod
    def setUp(cls) -> None:
        """Define a multi library example repo."""

        cls.revision = "e64923e69e"

        cls.bb_result_report_path = Path(
            "benchbuild/results/GenerateBlameReport"
        )
        cls.bb_result_lib_path = Path(
            cls.bb_result_report_path /
            f"TwoLibsOneProjectInteractionDiscreteLibsSingle"
            f"Project-cpp_projects@{cls.revision}" /
            "TwoLibsOneProjectInteractionDiscreteLibsSingleProject"
        )

        cls.elementalist = VaraTestRepoSource(
            project_name="TwoLibsOneProjectInteractionDiscreteLibsSingleProject",
            remote="LibraryAnalysisRepos"
            "/TwoLibsOneProjectInteractionDiscreteLibsSingleProject"
            "/Elementalist",
            local="TwoLibsOneProjectInteractionDiscreteLibsSingleProject"
            "/Elementalist",
            refspec="origin/HEAD",
            limit=None,
            shallow=False
        )

        cls.fire_lib = VaraTestRepoSubmodule(
            remote="LibraryAnalysisRepos"
            "/TwoLibsOneProjectInteractionDiscreteLibsSingleProject"
            "/fire_lib",
            local="TwoLibsOneProjectInteractionDiscreteLibsSingleProject"
            "/fire_lib",
            refspec="origin/HEAD",
            limit=None,
            shallow=False,
        )

        cls.water_lib = VaraTestRepoSubmodule(
            remote="LibraryAnalysisRepos"
            "/TwoLibsOneProjectInteractionDiscreteLibsSingleProject"
            "/water_lib",
            local="TwoLibsOneProjectInteractionDiscreteLibsSingleProject"
            "/water_lib",
            refspec="origin/HEAD",
            limit=None,
            shallow=False,
        )

    @run_in_test_environment(UnitTestFixtures.TEST_PROJECTS)
    def test_vara_test_repo_dir_creation(self) -> None:
        """Test if the needed directories of the main repo and its submodules
        are present."""

        mkdir("-p", self.bb_result_report_path)

        self.elementalist.version(
            f"{self.bb_result_report_path}/"
            f"TwoLibsOneProjectInteractionDiscreteLibsSingleProject"
            f"-cpp_projects@{self.revision}",
            version=self.revision
        )

        # Are directories present?
        self.assertTrue(
            isdir(
                f"{str(bb_cfg()['tmp_dir'])}/"
                f"TwoLibsOneProjectInteractionDiscreteLibsSingleProject"
            )
        )
        self.assertTrue(isdir(self.bb_result_lib_path))
        self.assertTrue(isdir(self.bb_result_lib_path / "Elementalist"))
        self.assertTrue(isdir(self.bb_result_lib_path / "fire_lib"))
        self.assertTrue(isdir(self.bb_result_lib_path / "water_lib"))
        self.assertTrue(
            isdir(
                self.bb_result_lib_path / "Elementalist" / "external" /
                "fire_lib"
            )
        )
        self.assertTrue(
            isdir(
                self.bb_result_lib_path / "Elementalist" / "external" /
                "water_lib"
            )
        )

    @run_in_test_environment(UnitTestFixtures.TEST_PROJECTS)
    def test_vara_test_repo_gitted_renaming(self) -> None:
        """Test if the .gitted files are correctly renamed back to their
        original git name."""
        self.elementalist.version(
            f"{self.bb_result_report_path}/"
            f"TwoLibsOneProjectInteractionDiscreteLibsSingleProject"
            f"-cpp_projects@{self.revision}",
            version=self.revision
        )

        # Are .gitted files correctly renamed?
        self.assertTrue(
            isdir(self.bb_result_lib_path / "Elementalist" / ".git")
        )
        self.assertTrue(isdir(self.bb_result_lib_path / "fire_lib" / ".git"))
        self.assertTrue(isdir(self.bb_result_lib_path / "water_lib" / ".git"))
        self.assertTrue(
            (self.bb_result_lib_path / "Elementalist" / ".gitmodules").exists()
        )

    @run_in_test_environment(UnitTestFixtures.TEST_PROJECTS)
    def test_vara_test_repo_lib_checkout(self) -> None:
        """Test if the repositories are checked out at the specified
        revision."""
        self.elementalist.version(
            f"{self.bb_result_report_path}/"
            f"TwoLibsOneProjectInteractionDiscreteLibsSingleProject"
            f"-cpp_projects@{self.revision}",
            version=self.revision
        )

        # Are repositories checked out at correct commit hash?
        with local.cwd(self.bb_result_lib_path / "Elementalist"):
            self.assertEqual(
                self.revision[:7],
                git('rev-parse', '--short', 'HEAD').rstrip()
            )

        with local.cwd(self.bb_result_lib_path / "fire_lib"):
            self.assertEqual(
                "ead5e00",
                git('rev-parse', '--short', 'HEAD').rstrip()
            )

        with local.cwd(self.bb_result_lib_path / "water_lib"):
            self.assertEqual(
                "58ec513",
                git('rev-parse', '--short', 'HEAD').rstrip()
            )

        with local.cwd(self.bb_result_lib_path / "earth_lib"):
            self.assertEqual(
                "1db6fbe",
                git('rev-parse', '--short', 'HEAD').rstrip()
            )

    def test_if_project_names_are_well_formed(self) -> None:
        """Tests if project names are well-formed, e.g., they must not contain a
        dash."""

        varats_cfg = create_new_varats_config()
        bb_cfg = create_new_bb_config(varats_cfg, True)
        loaded_project_paths: tp.List[str] = bb_cfg["plugins"]["projects"].value

        loaded_project_names = [
            project_path.rsplit(sep='.', maxsplit=1)[1]
            for project_path in loaded_project_paths
        ]
        for project_name in loaded_project_names:
            if '-' in project_name:
                self.fail(
                    f"The project name {project_name} must not contain the "
                    f"dash character."
                )


class TestProjectBinaryWrapper(unittest.TestCase):
    """Test if we can correctly setup and use the RevisionBinaryMap."""

    def test_execution_of_executable(self) -> None:
        """Check if we can execute an executable binary."""
        binary = ProjectBinaryWrapper(
            "ls", Path("/bin/ls"), BinaryType.EXECUTABLE
        )

        ret = binary()
        self.assertIsNotNone(ret)
        self.assertIsInstance(ret, str)

    def test_execution_of_libraries(self) -> None:
        """Check whether we fail when executing a shared/static library."""
        static_lib_binary = ProjectBinaryWrapper(
            "ls", Path("/bin/ls"), BinaryType.STATIC_LIBRARY
        )
        self.assertIsNone(static_lib_binary())

        shared_lib_binary = ProjectBinaryWrapper(
            "ls", Path("/bin/ls"), BinaryType.SHARED_LIBRARY
        )
        self.assertIsNone(shared_lib_binary())
