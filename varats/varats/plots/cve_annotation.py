"""Annotate CVE/CWE data to a plot."""
import typing as tp

from benchbuild.project import Project
from matplotlib import axes

from varats.mapping.commit_map import create_lazy_commit_map_loader
from varats.provider.cve.cve_provider import CVEProvider


def draw_cves(
    axis: axes.Axes, project: tp.Type[Project], revisions: tp.List[str],
    plot_kwargs: tp.Any
) -> None:
    """
    Annotates CVEs for a project in an existing plot.

    Args:
        axis: the axis to use for the plot
        project: the project to add CVEs for
        revisions: a list of revisions included in the plot in the order they
                   appear on the x-axis
        plot_kwargs: the arguments that specify a plots style
    """
    cmap = create_lazy_commit_map_loader(project.NAME)()
    revision_time_ids = [cmap.short_time_id(rev) for rev in revisions]

    cve_provider = CVEProvider.get_provider_for_project(project)
    for revision, cves in cve_provider.get_revision_cve_tuples():
        cve_time_id = cmap.time_id(revision)
        if cve_time_id in revision_time_ids:
            index = float(revisions.index(revision))
        else:
            # revision not in sample; draw line between closest samples
            index = len([x for x in revision_time_ids if x < cve_time_id]) - 0.5

        transform = axis.get_xaxis_transform()
        for cve in cves:
            axis.axvline(
                index,
                label=cve.cve_id,
                linewidth=plot_kwargs["cve_bug_line_width"],
                color=plot_kwargs["cve_bug_color"]
            )
            axis.text(
                index + 0.1,
                0,
                cve.cve_id,
                transform=transform,
                rotation=90,
                size=plot_kwargs["label_size"],
                color=plot_kwargs["cve_bug_color"],
                va=plot_kwargs["vertical_alignment"]
            )
