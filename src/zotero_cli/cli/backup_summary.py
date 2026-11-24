"""How `system backup` and `collection backup` tell the user what they wrote (Issue #656)."""

from zotero_cli.core.exceptions import PartialFailure
from zotero_cli.core.models import LibraryRef
from zotero_cli.core.services.backup_service import BackupReport
from zotero_cli.core.utils.terminal_safety import SafeConsole, safe_markup


def library_note(service: object) -> str:
    """` (group library 777)`, to be wrapped in `safe_markup` by the caller: the library a
    backup is reading (Issue #661), so a run against the wrong one is noticed before it
    finishes."""
    library = getattr(service, "library", None)
    if not isinstance(library, LibraryRef):
        return ""
    return f" ({library.type} library {library.id})"


def finish_backup(report: BackupReport, output: str, console: SafeConsole) -> None:
    """Prints the result. A backup that could not save everything is not "complete": the
    archive is kept (it is the best copy there is) and the command exits with the
    partial-failure status, so a script, or a person about to delete the originals,
    can tell. Linked files are expected gaps and only get a note."""
    if report.skipped:
        console.print(
            f"[yellow]Note:[/yellow] {len(report.skipped)} linked file(s) live on your own "
            "computer, which the Web API cannot back up. Their records are in the archive; "
            "they are listed in errors.log inside it."
        )
    if not report.complete:
        console.print(f"[yellow]Backup written with problems:[/yellow] {safe_markup(output)}")
        raise PartialFailure(
            f"the backup is incomplete: {len(report.errors)} problem(s), for example: "
            f"{report.errors[0]} (all of them are in errors.log inside {output})"
        )
    console.print(f"[bold green]Backup complete:[/bold green] {safe_markup(output)}")
