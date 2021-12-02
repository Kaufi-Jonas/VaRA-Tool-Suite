"""
This module provides a reusable version header for all yaml reports generated by
VaRA.

The version header specifies the type of the following yaml file and the
version.
"""

import typing as tp


class WrongYamlFileType(Exception):
    """Exception raised for miss matches of the file type."""

    def __init__(self, expected_type: str, actual_type: str) -> None:
        super().__init__(
            f"Expected FileType: '{expected_type}' but got '{actual_type}'"
        )


class WrongYamlFileVersion(Exception):
    """Exception raised for miss matches of the file version."""

    def __init__(self, expected_version: int, actual_version: int):
        super().__init__(
            f"Expected minimal version: '{expected_version}' " +
            f"but got version '{actual_version}'"
        )


class NoVersionHeader(Exception):
    """Exception raised for wrong yaml documents."""

    def __init__(self) -> None:
        super().__init__("No VersionHeader found, got wrong yaml document.")


class VersionHeader():
    """VersionHeader describing the type and version of the following yaml
    file."""

    def __init__(self, yaml_doc: tp.Dict[str, tp.Any]) -> None:
        if 'DocType' not in yaml_doc or 'Version' not in yaml_doc:
            raise NoVersionHeader()

        self.__doc_type = str(yaml_doc['DocType'])
        self.__version = int(yaml_doc['Version'])

    @classmethod
    def from_yaml_doc(cls, yaml_doc: tp.Dict[str, tp.Any]) -> 'VersionHeader':
        """
        Creates a VersionHeader object from a yaml dict.

        Args:
            yaml_doc: version header yaml document
        """
        return cls(yaml_doc)

    @classmethod
    def from_version_number(
        cls, doc_type: str, version: int
    ) -> 'VersionHeader':
        """
        Creates a new VersionHeader object from a ``doc_type`` string and a
        version number.

        Args:
            doc_type: type of the document that should follow the version header
            version: the current version number
        """
        yaml_doc = {'DocType': doc_type, 'Version': version}
        return cls(yaml_doc)

    @property
    def doc_type(self) -> str:
        """Type of the following yaml file."""
        return self.__doc_type

    def is_type(self, type_name: str) -> bool:
        """
        Checks if the type of the following yaml file is ``type_name``.

        Args:
            type_name: of the possible following yaml document
        """
        return type_name == self.doc_type

    def raise_if_not_type(self, type_name: str) -> None:
        """
        Checks if the type of the following yaml file is type_name, otherwise,
        raises an exception.

        Args:
            type_name: of the possible following yaml document
        """
        if not self.is_type(type_name):
            raise WrongYamlFileType(type_name, self.doc_type)

    @property
    def version(self) -> int:
        """Document version number."""
        return self.__version

    def raise_if_version_is_less_than(self, version_bound: int) -> None:
        """
        Checks if the current version is equal or bigger that version_bound,
        otherwise, raises an exception.

        Args:
            version_bound: minimal version that is expected
        """
        if self.version < version_bound:
            raise WrongYamlFileVersion(version_bound, self.version)

    def get_dict(self) -> tp.Dict[str, tp.Union[str, int]]:
        """Returns the version header as a dict."""
        doc: tp.Dict[str, tp.Union[str, int]] = {}
        doc['DocType'] = self.__doc_type
        doc['Version'] = self.__version
        return doc
