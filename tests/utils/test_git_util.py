"""Test VaRA git utilities."""
import unittest
from pathlib import Path

from benchbuild.utils.revision_ranges import RevisionRange
from plumbum import local

from varats.project.project_util import (
    get_local_project_git,
    get_local_project_git_path,
    BinaryType,
)
from varats.utils.git_util import (
    ChurnConfig,
    CommitRepoPair,
    FullCommitHash,
    ShortCommitHash,
    calc_code_churn,
    calc_commit_code_churn,
    get_all_revisions_between,
    get_current_branch,
    get_initial_commit,
    RevisionBinaryMap,
)


class TestGitInteractionHelpers(unittest.TestCase):
    """Test if the different git helper classes work."""

    def test_get_current_branch(self):
        """Check if we can correctly retrieve the current branch of a repo."""
        repo = get_local_project_git("brotli")

        repo.checkout(repo.lookup_branch('master'))

        self.assertEqual(get_current_branch(repo.workdir), 'master')

    def test_get_initial_commit(self) -> None:
        """Check if we can correctly retrieve the inital commit of a repo."""
        repo = get_local_project_git("FeaturePerfCSCollection")

        with local.cwd(repo.workdir):
            inital_commit = get_initial_commit()

            self.assertEqual(
                FullCommitHash("4d84c8f80ec2db3aaa880d323f7666752c4be51d"),
                inital_commit
            )

    def test_get_initial_commit_with_specified_path(self) -> None:
        """Check if we can correctly retrieve the inital commit of a repo."""
        inital_commit = get_initial_commit(
            get_local_project_git_path("FeaturePerfCSCollection")
        )

        self.assertEqual(
            FullCommitHash("4d84c8f80ec2db3aaa880d323f7666752c4be51d"),
            inital_commit
        )

    def test_get_all_revisions_between_full(self):
        """Check if the correct all revisions are correctly found."""
        repo = get_local_project_git("brotli")
        with local.cwd(repo.workdir):
            revs = get_all_revisions_between(
                '5692e422da6af1e991f9182345d58df87866bc5e',
                '2f9277ff2f2d0b4113b1ffd9753cc0f6973d354a', FullCommitHash
            )

            self.assertSetEqual(
                set(revs), {
                    FullCommitHash("5692e422da6af1e991f9182345d58df87866bc5e"),
                    FullCommitHash("2a51a85aa86abb4c294c65fab57f3d9c69f10080"),
                    FullCommitHash("63be8a99401992075c23e99f7c84de1c653e39e2"),
                    FullCommitHash("2f9277ff2f2d0b4113b1ffd9753cc0f6973d354a")
                }
            )

    def test_get_all_revisions_between_short(self):
        """Check if the correct all revisions are correctly found."""
        repo = get_local_project_git("brotli")
        with local.cwd(repo.workdir):
            revs = get_all_revisions_between(
                '5692e422da6af1e991f9182345d58df87866bc5e',
                '2f9277ff2f2d0b4113b1ffd9753cc0f6973d354a', ShortCommitHash
            )

            self.assertSetEqual(
                set(revs), {
                    ShortCommitHash("5692e422da"),
                    ShortCommitHash("2a51a85aa8"),
                    ShortCommitHash("63be8a9940"),
                    ShortCommitHash("2f9277ff2f")
                }
            )


class TestChurnConfig(unittest.TestCase):
    """Test if ChurnConfig sets languages correctly."""

    def test_enable_language(self):
        init_config = ChurnConfig.create_default_config()
        self.assertFalse(init_config.is_enabled('c'))
        init_config.enable_language(ChurnConfig.Language.CPP)
        self.assertFalse(init_config.is_enabled('c'))
        init_config.enable_language(ChurnConfig.Language.C)
        self.assertTrue(init_config.is_enabled('c'))

    def test_initial_config(self):
        init_config = ChurnConfig.create_default_config()
        self.assertTrue(init_config.include_everything)
        self.assertListEqual(init_config.enabled_languages, [])

    def test_c_language_config(self):
        c_style_config = ChurnConfig.create_c_language_config()
        self.assertTrue(c_style_config.is_enabled('h'))
        self.assertTrue(c_style_config.is_enabled('c'))

    def test_c_style_config(self):
        c_style_config = ChurnConfig.create_c_style_languages_config()
        self.assertTrue(c_style_config.is_enabled('h'))
        self.assertTrue(c_style_config.is_enabled('c'))
        self.assertTrue(c_style_config.is_enabled('hpp'))
        self.assertTrue(c_style_config.is_enabled('cpp'))
        self.assertTrue(c_style_config.is_enabled('hxx'))
        self.assertTrue(c_style_config.is_enabled('cxx'))

    def test_enabled_language(self):
        c_config = ChurnConfig.create_c_language_config()
        self.assertTrue(c_config.is_language_enabled(ChurnConfig.Language.C))
        self.assertFalse(c_config.is_language_enabled(ChurnConfig.Language.CPP))

    def test_extensions_repr_gen(self):
        c_config = ChurnConfig.create_c_language_config()
        self.assertEqual(c_config.get_extensions_repr(), ["c", "h"])
        self.assertEqual(
            c_config.get_extensions_repr(prefix="*."), ["*.c", "*.h"]
        )
        self.assertEqual(c_config.get_extensions_repr(suffix="|"), ["c|", "h|"])

        c_style_config = ChurnConfig.create_c_style_languages_config()
        self.assertEqual(
            c_style_config.get_extensions_repr(),
            ["c", "cpp", "cxx", "h", "hpp", "hxx"]
        )
        self.assertEqual(
            c_style_config.get_extensions_repr(prefix="*."),
            ["*.c", "*.cpp", "*.cxx", "*.h", "*.hpp", "*.hxx"]
        )
        self.assertEqual(
            c_style_config.get_extensions_repr(suffix="|"),
            ["c|", "cpp|", "cxx|", "h|", "hpp|", "hxx|"]
        )


class TestCommitRepoPair(unittest.TestCase):
    """Test driver for the CommitRepoPair class."""

    @classmethod
    def setUpClass(cls):
        cls.cr_pair = CommitRepoPair(
            FullCommitHash("4200000000000000000000000000000000000000"),
            "foo_repo"
        )

    def test_commit_hash(self):
        self.assertEqual(
            self.cr_pair.commit_hash,
            FullCommitHash("4200000000000000000000000000000000000000")
        )

    def test_repo_name(self):
        self.assertEqual(self.cr_pair.repository_name, "foo_repo")

    def test_less_equal(self):
        """Tests that two equal pairs are not less."""
        cr_pair_1 = CommitRepoPair(
            FullCommitHash("4200000000000000000000000000000000000000"),
            "foo_repo"
        )
        cr_pair_2 = CommitRepoPair(
            FullCommitHash("4200000000000000000000000000000000000000"),
            "foo_repo"
        )

        self.assertFalse(cr_pair_1 < cr_pair_2)

    def test_less_commit(self):
        """Tests that a smaller commit is less."""
        cr_pair_1 = CommitRepoPair(
            FullCommitHash("4100000000000000000000000000000000000000"),
            "foo_repo"
        )
        cr_pair_2 = CommitRepoPair(
            FullCommitHash("4200000000000000000000000000000000000000"),
            "foo_repo"
        )

        self.assertTrue(cr_pair_1 < cr_pair_2)

    def test_less_repo(self):
        """Tests that a smaller repo is less, if the commits are equal."""
        cr_pair_1 = CommitRepoPair(
            FullCommitHash("4200000000000000000000000000000000000000"),
            "foo_repo"
        )
        cr_pair_2 = CommitRepoPair(
            FullCommitHash("4200000000000000000000000000000000000000"),
            "boo_repo"
        )

        self.assertFalse(cr_pair_1 < cr_pair_2)

    def tests_less_something_other(self):
        self.assertFalse(self.cr_pair < 42)

    def test_equal_equal(self):
        """Tests that two equal pairs are equal."""
        cr_pair_1 = CommitRepoPair(
            FullCommitHash("4200000000000000000000000000000000000000"),
            "foo_repo"
        )
        cr_pair_2 = CommitRepoPair(
            FullCommitHash("4200000000000000000000000000000000000000"),
            "foo_repo"
        )

        self.assertTrue(cr_pair_1 == cr_pair_2)

    def test_equal_commit(self):
        """Tests that two different commits are not equal."""
        cr_pair_1 = CommitRepoPair(
            FullCommitHash("4100000000000000000000000000000000000000"),
            "foo_repo"
        )
        cr_pair_2 = CommitRepoPair(
            FullCommitHash("4200000000000000000000000000000000000000"),
            "foo_repo"
        )

        self.assertFalse(cr_pair_1 == cr_pair_2)

    def test_equal_repo(self):
        """Tests that two different commits are not equal."""
        cr_pair_1 = CommitRepoPair(
            FullCommitHash("4200000000000000000000000000000000000000"),
            "bar_repo"
        )
        cr_pair_2 = CommitRepoPair(
            FullCommitHash("4200000000000000000000000000000000000000"),
            "foo_repo"
        )

        self.assertFalse(cr_pair_1 == cr_pair_2)

    def tests_equal_something_other(self):
        self.assertFalse(self.cr_pair == 42)

    def test_to_string(self):
        self.assertEqual(
            str(self.cr_pair),
            "foo_repo[4200000000000000000000000000000000000000]"
        )


class TestCodeChurnCalculation(unittest.TestCase):
    """Test if we correctly compute code churn."""

    def test_one_commit_diff(self):
        """Check if we get the correct code churn for a single commit."""

        repo = get_local_project_git("brotli")

        files_changed, insertions, deletions = calc_commit_code_churn(
            repo, repo.get("0c5603e07bed1d5fbb45e38f9bdf0e4560fde3f0"),
            ChurnConfig.create_c_style_languages_config()
        )

        self.assertEqual(files_changed, 1)
        self.assertEqual(insertions, 2)
        self.assertEqual(deletions, 2)

    def test_one_commit_diff_2(self):
        """Check if we get the correct code churn for a single commit."""

        repo = get_local_project_git("brotli")

        files_changed, insertions, deletions = calc_commit_code_churn(
            repo, repo.get("fc823290a76a260b7ba6f47ab5f52064a0ce19ff"),
            ChurnConfig.create_c_style_languages_config()
        )

        self.assertEqual(files_changed, 1)
        self.assertEqual(insertions, 5)
        self.assertEqual(deletions, 0)

    def test_one_commit_diff_3(self):
        """Check if we get the correct code churn for a single commit."""

        repo = get_local_project_git("brotli")

        files_changed, insertions, deletions = calc_commit_code_churn(
            repo, repo.get("924b2b2b9dc54005edbcd85a1b872330948cdd9e"),
            ChurnConfig.create_c_style_languages_config()
        )

        self.assertEqual(files_changed, 3)
        self.assertEqual(insertions, 38)
        self.assertEqual(deletions, 7)

    def test_one_commit_diff_ignore_non_c_cpp_files(self):
        """Check if we get the correct code churn for a single commit but only
        consider code changes."""

        repo = get_local_project_git("brotli")

        files_changed, insertions, deletions = calc_commit_code_churn(
            repo, repo.get("f503cb709ca181dbf5c73986ebac1b18ac5c9f63"),
            ChurnConfig.create_c_style_languages_config()
        )

        self.assertEqual(files_changed, 1)
        self.assertEqual(insertions, 11)
        self.assertEqual(deletions, 4)

    def test_commit_range(self):
        """Check if we get the correct code churn for commit range."""

        repo = get_local_project_git("brotli")

        files_changed, insertions, deletions = calc_code_churn(
            repo, repo.get("36ac0feaf9654855ee090b1f042363ecfb256f31"),
            repo.get("924b2b2b9dc54005edbcd85a1b872330948cdd9e"),
            ChurnConfig.create_c_style_languages_config()
        )

        self.assertEqual(files_changed, 3)
        self.assertEqual(insertions, 49)
        self.assertEqual(deletions, 11)


class TestRevisionBinaryMap(unittest.TestCase):
    """Test if we can correctly setup and use the RevisionBinaryMap."""

    rv_map: RevisionBinaryMap

    def setUp(self) -> None:
        self.rv_map = RevisionBinaryMap(
            get_local_project_git_path("FeaturePerfCSCollection")
        )

    def test_specification_of_always_valid_binaries(self) -> None:
        """Check if we can add binaries to the map."""
        self.rv_map.specify_binary(
            "build/bin/SingleLocalSimple", BinaryType.EXECUTABLE
        )

        self.assertIn("SingleLocalSimple", self.rv_map)

    def test_specification_validity_range_binaries(self) -> None:
        """Check if we can add binaries to the map that are only valid in a
        specific range."""
        self.rv_map.specify_binary(
            "build/bin/SingleLocalMultipleRegions",
            BinaryType.EXECUTABLE,
            only_valid_in=RevisionRange("162db88346", "master")
        )

        self.assertIn("SingleLocalMultipleRegions", self.rv_map)

    def test_specification_binaries_with_special_name(self) -> None:
        """Check if we can add binaries that have a special name."""
        self.rv_map.specify_binary(
            "build/bin/SingleLocalSimple",
            BinaryType.EXECUTABLE,
            override_binary_name="Overridden"
        )

        self.assertIn("Overridden", self.rv_map)

    def test_specification_binaries_with_special_entry_point(self) -> None:
        """Check if we can add binaries that have a special entry point."""
        self.rv_map.specify_binary(
            "build/bin/SingleLocalSimple",
            BinaryType.EXECUTABLE,
            override_entry_point="build/bin/OtherSLSEntry"
        )

        test_query = self.rv_map[ShortCommitHash("745424e3ae")]

        self.assertEqual(
            "build/bin/OtherSLSEntry", str(test_query[0].entry_point)
        )
        self.assertIsInstance(test_query[0].entry_point, Path)

    def test_wrong_contains_check(self) -> None:
        """Check if wrong values are correctly shows as not in the map."""
        self.rv_map.specify_binary(
            "build/bin/SingleLocalSimple", BinaryType.EXECUTABLE
        )

        self.assertNotIn("WrongFilename", self.rv_map)

        obj_with_wrong_type = object()
        self.assertNotIn(obj_with_wrong_type, self.rv_map)

    def test_valid_binary_lookup(self) -> None:
        """Check if we can correctly determine the list of valid binaries for a
        specified revision."""
        self.rv_map.specify_binary(
            "build/bin/SingleLocalSimple", BinaryType.EXECUTABLE
        )
        self.rv_map.specify_binary(
            "build/bin/SingleLocalMultipleRegions",
            BinaryType.EXECUTABLE,
            only_valid_in=RevisionRange("162db88346", "master")
        )

        test_query = self.rv_map[ShortCommitHash("162db88346")]
        self.assertSetEqual({x.name for x in test_query},
                            {"SingleLocalSimple", "SingleLocalMultipleRegions"})

        test_query = self.rv_map[ShortCommitHash("745424e3ae")]
        self.assertSetEqual({x.name for x in test_query}, {"SingleLocalSimple"})
