"""CLI entry point for DJ CrateDigger."""

import click


@click.group()
def cli():
    """DJ CrateDigger — Library Scanner & Cleanup Tool."""
    pass


# Register all submodule commands and groups
from .scan import scan, fix_tags, fix_dupes, fix_filenames, fix_all  # noqa: E402, F401
from .analysis import analyze, scan_essentia, enrich, enrich_essentia  # noqa: E402, F401
from .gig import gig, cues  # noqa: E402, F401
from .streaming import spotify, youtube, dig_sleeping  # noqa: E402, F401
from .tools import watch, identify, profile, report, pipeline  # noqa: E402, F401
from .dig import dig, dig_label, dig_artist, dig_weekly  # noqa: E402, F401


def main():
    cli()
