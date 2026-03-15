"""CLI entry point for DJ CrateDigger."""

import click


@click.group()
def cli():
    """DJ CrateDigger — Library Scanner & Cleanup Tool."""
    pass


# Register all submodule commands and groups
from .analysis import analyze, enrich, enrich_essentia, scan_essentia  # noqa: E402, F401
from .dig import dig, dig_artist, dig_label, dig_weekly  # noqa: E402, F401
from .gig import cues, gig  # noqa: E402, F401
from .scan import fix_all, fix_dupes, fix_filenames, fix_tags, scan  # noqa: E402, F401
from .streaming import dig_sleeping, spotify, youtube  # noqa: E402, F401
from .play import play  # noqa: E402, F401
from .tools import identify, pipeline, profile, report, watch  # noqa: E402, F401
from .intake import intake  # noqa: E402, F401
from .preflight_cmd import preflight  # noqa: E402, F401


def main():
    cli()
