"""Standalone SQLite snapshot reference; see README for scope and provenance."""
from contextlib import closing
from pathlib import Path
import sqlite3


def copy_database(source: Path, destination: Path) -> Path:
    """Copy an existing SQLite database into a new path, never replace a target.

    Works for backup or restoration to an isolated directory. Attachments are not
    included. The caller owns directory access and coordinates the wider backup.
    A failed copy removes only the newly-created target, never the source.
    """
    source = Path(source).resolve(strict=True)
    destination = Path(destination).absolute()
    if not source.is_file():
        raise ValueError("Source must be an existing database file")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation closes the exists()/create race for ordinary writers.
    with destination.open("xb"):
        pass
    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as src:
            with closing(sqlite3.connect(destination)) as dst:
                src.backup(dst)
                results = [row[0] for row in dst.execute("PRAGMA quick_check")]
                if results != ["ok"]:
                    raise sqlite3.DatabaseError("Copied database failed quick_check")
    except BaseException:
        # Destination was exclusively created above and is not a live user DB.
        destination.unlink(missing_ok=True)
        raise
    return destination
