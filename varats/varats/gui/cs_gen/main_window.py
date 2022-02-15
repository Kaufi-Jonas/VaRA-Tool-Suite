import sys
import time
import typing as tp
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path

import benchbuild as bb
import pygit2
from PyQt5 import Qt
from PyQt5.QtCore import QModelIndex
from PyQt5.QtWidgets import (
    QMainWindow,
    QApplication,
    QMessageBox,
    QTableWidgetItem,
)

from varats.base.sampling_method import NormalSamplingMethod
from varats.gui.cs_gen.main_window_ui import Ui_MainWindow
from varats.mapping.commit_map import create_lazy_commit_map_loader
from varats.paper.case_study import CaseStudy, store_case_study
from varats.paper_mgmt.case_study import (
    extend_with_extra_revs,
    extend_with_distrib_sampling,
)
from varats.project.project_util import (
    get_loaded_vara_projects,
    get_local_project_git_path,
    get_project_cls_by_name,
)
from varats.projects.discover_projects import initialize_projects
from varats.tools.research_tools.vara_manager import ProcessManager
from varats.ts_utils.cli_util import initialize_cli_tool
from varats.utils import settings
from varats.utils.git_util import (
    get_initial_commit,
    get_all_revisions_between,
    FullCommitHash,
    ShortCommitHash,
    create_commit_lookup_helper,
)
from varats.utils.settings import vara_cfg


class GenerationStrategie(Enum):
    SELECTREVISION = 0
    SAMPLE = 1


class CsGenMainWindow(QMainWindow, Ui_MainWindow):

    def __init__(self):
        super().__init__()
        self.selected_commit = None
        self.setupUi(self)
        initialize_projects()
        projects = get_loaded_vara_projects()
        self.selected_project = None
        self.revision_list_project = None
        self.project_names = [
            project.NAME
            for project in projects
            if project.GROUP not in ["test_projects", "perf_tests"]
        ]
        self.project_list.addItems(self.project_names)
        self.project_list.clicked['QModelIndex'].connect(self.show_project_data)
        self.sampling_method.addItems([
            x.name()
            for x in NormalSamplingMethod.normal_sampling_method_types()
        ])
        self.revision_list.cellClicked.connect(self.show_revision_data)
        self.select_specific.clicked.connect(self.show_revisions_of_project)
        self.sample.clicked.connect(self.sample_view)
        self.generate.clicked.connect(self.gen)
        self.show()

    def sample_view(self):
        self.strategie_forms.setCurrentIndex(GenerationStrategie.SAMPLE.value)
        self.strategie_forms.update()

    def gen(self):
        cmap = create_lazy_commit_map_loader(
            self.revision_list_project, None, 'HEAD', None
        )()
        case_study = CaseStudy(self.revision_list_project, 0)
        paper_config = vara_cfg()["paper_config"]["current_config"].value
        path = Path(
            vara_cfg()["paper_config"]["folder"].value
        ) / (paper_config + f"/{self.revision_list_project}_0.case_study")

        if self.strategie_forms.currentIndex(
        ) == GenerationStrategie.SAMPLE.value:
            self.gen_sample(cmap, case_study)
        elif self.strategie_forms.currentIndex(
        ) == GenerationStrategie.SELECTREVISION.value:
            self.gen_specific(cmap, case_study)
        store_case_study(case_study, path)

    def gen_sample(self, cmap, case_study):
        sampling_method = NormalSamplingMethod.get_sampling_method_type(
            self.sampling_method.currentText()
        )
        extend_with_distrib_sampling(
            case_study, cmap, sampling_method(), 0, self.num_revs.value(), True
        )

    def gen_specific(self, cmap, case_study):
        selected_rows = self.revision_list.selectionModel().selectedRows(0)
        selected_commits = [row.data() for row in selected_rows]
        extend_with_extra_revs(case_study, cmap, selected_commits, 0)
        self.revision_list.clearSelection()
        self.revision_list.update()

    def show_project_data(self, index: QModelIndex):
        project_name = index.data()
        if self.selected_project != project_name:
            self.selected_project = project_name
            project = get_project_cls_by_name(project_name)
            project_info = f"{project_name.upper()} : \nDomain: {project.DOMAIN}\nSource: {bb.source.primary(*project.SOURCE).remote}"
            self.project_details.setText(project_info)
            self.project_details.update()
            if self.strategie_forms.currentIndex(
            ) == GenerationStrategie.SELECTREVISION.value:
                self.show_revisions_of_project()

    def show_revisions_of_project(self):
        self.strategie_forms.setCurrentIndex(
            GenerationStrategie.SELECTREVISION.value
        )
        if self.selected_project != self.revision_list_project:
            self.revision_list.clearContents()
            self.revision_list.setRowCount(0)
            self.revision_list.update()
            print(time.time())
            self.revision_details.setText("Loading Revisions")
            self.revision_details.update()
            git_path = get_local_project_git_path(self.selected_project)
            initial_commit = get_initial_commit(git_path).hash
            commits = get_all_revisions_between(
                initial_commit, 'HEAD', ShortCommitHash, git_path
            )
            self.revision_list.setRowCount(len(commits))
            commit_lookup_helper = create_commit_lookup_helper(
                self.selected_project
            )
            for n, commit_hash in enumerate(commits):
                commit: pygit2.Commit = commit_lookup_helper(commit_hash)
                self.revision_list.setItem(
                    n, 0,
                    QTableWidgetItem(
                        ShortCommitHash.from_pygit_commit(commit).short_hash
                    )
                )
                self.revision_list.setItem(
                    n, 1, QTableWidgetItem(commit.author.name)
                )
                tzinfo = timezone(timedelta(minutes=commit.author.offset))
                dt = datetime.fromtimestamp(float(commit.author.time), tzinfo)
                timestr = dt.strftime('%c %z')
                self.revision_list.setItem(n, 2, QTableWidgetItem(timestr))
            self.revision_list.resizeColumnsToContents()
            self.revision_list.setSortingEnabled(True)
            self.revision_details.clear()
            self.revision_details.update()
            print(time.time())
            self.revision_list.update()
            self.revision_list_project = self.selected_project

    def show_revision_data(self, row, column):
        index = self.revision_list.item(row, 0)
        commit_hash = ShortCommitHash(index.text())
        commit_lookup_helper = create_commit_lookup_helper(
            self.selected_project
        )
        commit: pygit2.Commit = commit_lookup_helper(commit_hash)
        commit_info = f"{commit.hex}\nAuthor:{commit.author.name},{commit.author.email}\nMsg:{commit.message}"
        self.selected_commit = commit_hash.hash
        self.revision_details.setText(commit_info)
        self.revision_details.update()


class VaRATSGui:
    """Start VaRA-TS grafical user interface for graphs."""

    def __init__(self) -> None:
        if hasattr(Qt, 'AA_EnableHighDpiScaling'):
            QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
            QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

        self.app = QApplication(sys.argv)

        if settings.vara_cfg()["config_file"].value is None:
            err = QMessageBox()
            err.setIcon(QMessageBox.Warning)
            err.setWindowTitle("Missing config file.")
            err.setText(
                "Could not find VaRA config file.\n"
                "Should we create a config file in the current folder?"
            )

            err.setStandardButtons(
                tp.cast(
                    QMessageBox.StandardButtons,
                    QMessageBox.Yes | QMessageBox.No
                )
            )
            answer = err.exec_()
            if answer == QMessageBox.Yes:
                settings.save_config()
            else:
                sys.exit()

        self.main_window = CsGenMainWindow()

    def main(self) -> None:
        """Setup and Run Qt application."""
        ret = self.app.exec_()
        ProcessManager.shutdown()
        sys.exit(ret)


def main() -> None:
    """Start VaRA-TS driver and run application."""
    initialize_cli_tool()
    driver = VaRATSGui()
    driver.main()


if __name__ == '__main__':
    main()
