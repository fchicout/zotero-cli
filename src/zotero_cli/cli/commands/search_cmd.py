import argparse
from itertools import islice
from typing import Any, Dict, Iterable, Optional

from rich.markup import escape
from rich.table import Table

from zotero_cli.cli.base import BaseCommand, CommandRegistry
from zotero_cli.cli.flags import LIST_FORMAT_HELP, LIST_FORMATS, add_format_flag
from zotero_cli.cli.presenters import records
from zotero_cli.core.exceptions import NotFound, UsageError
from zotero_cli.core.models import ZoteroQuery
from zotero_cli.core.utils import search_filters
from zotero_cli.core.utils.terminal_safety import SafeConsole as Console
from zotero_cli.core.utils.terminal_safety import safe_markup
from zotero_cli.core.zotero_item import ZoteroItem
from zotero_cli.infra.factory import GatewayFactory

console = Console()


@CommandRegistry.register
class SearchCommand(BaseCommand):
    name = "search"
    help = "Search for items in the Zotero library"

    def register_args(self, parser: argparse.ArgumentParser) -> None:
        parser.description = "Performs a fast, targeted search across your Zotero library to find items matching keywords, titles, or DOIs."
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        parser.epilog = """
Examples
--------
Scenario: Finding a paper's key for inspection
Problem: I know I have a paper about "Transformer" architectures by "Vaswani" but I don't remember its key.
Action:  zotero-cli search "Vaswani Transformer"
Result:  The CLI displays all matching papers, and I can see the key ABCD1234 for the specific paper I need.

Scenario: Feeding the hits to a script
Action:  zotero-cli search "Vaswani Transformer" --format json
Result:  A JSON list on stdout (key, title, authors, year, doi); progress messages go to stderr.

Notes
-----
• Common Failure Modes: Attempting to search for common terms without a --limit in a very large library.
• Safety Tips: Use quotes for multi-word queries. Search is case-insensitive.

Documentation: https://github.com/fchicout/zotero-cli/tree/main/docs/help_specs/search.md
"""
        parser.add_argument(
            "query", nargs="?", help="Keyword search (matches title, creator, or year)"
        )
        parser.add_argument("--doi", help="Search by exact DOI")
        parser.add_argument("--title", help="Search by title substring")
        parser.add_argument("--limit", type=int, default=50, help="Limit results (default: 50)")
        parser.add_argument(
            "--start", type=int, default=0, help="Skip this many results first (paging)"
        )
        parser.add_argument(
            "--tag",
            action="append",
            help="Only items with this tag; repeat to require several. "
            "'a || b' means either; to exclude a tag write --tag=-name",
        )
        parser.add_argument(
            "--type",
            dest="item_type",
            help="Only this item type, e.g. journalArticle, book, note ('a || b' for either)",
        )
        parser.add_argument(
            "--collection", help="Only items filed in this collection (name or key)"
        )
        parser.add_argument(
            "--year", help="Publication year or range: 2020, 2018-2022, 2018- or -2022"
        )
        parser.add_argument("--added-since", help="Only items added on or after YYYY-MM-DD")
        parser.add_argument("--added-until", help="Only items added on or before YYYY-MM-DD")
        parser.add_argument(
            "--fulltext",
            action="store_true",
            help="Search inside the PDFs' text for every word of the query, best match first "
            "(needs --offline and a Zotero that keeps its full-text index in fulltext.sqlite)",
        )
        parser.add_argument(
            "--sort",
            choices=["date", "dateAdded", "dateModified", "title", "creator", "itemType"],
            help="Sort results by this field (default: date)",
        )
        parser.add_argument(
            "--direction", choices=["asc", "desc"], help="Sort direction (default: desc)"
        )
        add_format_flag(parser, choices=LIST_FORMATS, help=LIST_FORMAT_HELP)

    _COLUMNS = [
        records.Column("key", "Key"),
        records.Column("title", "Title"),
        records.Column("authors", "Authors"),
        records.Column("year", "Year"),
        records.Column("doi", "DOI"),
    ]

    _SCORE_COLUMN = records.Column("score", "Score", justify="right")

    @staticmethod
    def _record(item: ZoteroItem, score: Optional[float] = None) -> dict:
        row: Dict[str, Any] = {
            "key": item.key,
            "title": item.title or "",
            "authors": list(item.authors),
            "year": item.date[:4] if item.date else "",
            "doi": item.doi or "",
        }
        if score is not None:
            row["score"] = score
        return row

    @staticmethod
    def _build_query(
        text: Optional[str], args: argparse.Namespace, collection_key: Optional[str]
    ) -> ZoteroQuery:
        query = ZoteroQuery(
            q=text,
            qmode="titleCreatorYear",
            item_type=args.item_type,
            tag=args.tag or None,
            collection=collection_key,
        )
        if args.sort:
            query.sort = args.sort
        if args.direction:
            query.direction = args.direction
        return query

    @staticmethod
    def _resolve_collection(args: argparse.Namespace, name_or_key: Optional[str]) -> Optional[str]:
        if not name_or_key:
            return None
        service = GatewayFactory.get_collection_service(force_user=getattr(args, "user", False))
        key = service.resolve_collection(name_or_key)
        if not key:
            raise NotFound(f"Collection '{name_or_key}' not found.")
        return key

    # Options a caller may leave out (tests and scripts build their own Namespace).
    _OPTION_DEFAULTS = {
        "start": 0,
        "tag": None,
        "item_type": None,
        "collection": None,
        "year": None,
        "added_since": None,
        "added_until": None,
        "sort": None,
        "direction": None,
        "fulltext": False,
    }

    def execute(self, args: argparse.Namespace) -> None:
        args = argparse.Namespace(**{**self._OPTION_DEFAULTS, **vars(args)})
        force_user = getattr(args, "user", False)
        gateway = GatewayFactory.get_zotero_gateway(force_user=force_user)

        fmt = getattr(args, "format", "table")
        # Progress goes to stderr when stdout is carrying data.
        console = Console() if fmt == "table" else Console(stderr=True)

        if args.start < 0:
            raise UsageError("--start can't be negative.")
        years = search_filters.parse_year_range(args.year) if args.year else None
        added_since = (
            search_filters.parse_day(args.added_since, "--added-since")
            if args.added_since
            else None
        )
        added_until = (
            search_filters.parse_day(args.added_until, "--added-until")
            if args.added_until
            else None
        )
        has_filter = any(
            [args.tag, args.item_type, args.collection, years, added_since, added_until]
        )

        scores: Dict[str, float] = {}
        if args.fulltext:
            if args.doi or args.title:
                raise UsageError(
                    "--fulltext looks for the query's words in the PDFs' text; "
                    "it can't be combined with --doi or --title."
                )
            if args.sort or args.direction:
                raise UsageError(
                    "--fulltext ranks by relevance; --sort and --direction don't apply."
                )
            if not args.query:
                raise UsageError('--fulltext needs words to look for: search --fulltext "words".')
            console.print(f"Searching the full text for: [cyan]{escape(args.query)}[/cyan]...")
            collection_key = self._resolve_collection(args, args.collection)
            ranked = gateway.search_fulltext(
                args.query, self._build_query(None, args, collection_key)
            )
            scores = {item.key: score for item, score in ranked}
            hits: Iterable[ZoteroItem] = (item for item, _ in ranked)
        elif args.doi:
            if has_filter:
                raise UsageError("--doi names one item and can't be combined with filters.")
            console.print(f"Searching for DOI: [cyan]{escape(args.doi)}[/cyan]...")
            hits = gateway.get_items_by_doi(args.doi)
        elif args.title or args.query or has_filter:
            text = args.title or args.query
            if args.title:
                console.print(f"Searching for title: [cyan]{escape(args.title)}[/cyan]...")
            elif text:
                console.print(f"Searching for: [cyan]{escape(text)}[/cyan]...")
            else:
                console.print("Searching with filters...")
            collection_key = self._resolve_collection(args, args.collection)
            hits = gateway.search_items(self._build_query(text, args, collection_key))
        else:
            raise UsageError("Provide a query, --doi, --title or a filter such as --tag.")

        if years is not None or added_since is not None or added_until is not None:
            hits = (
                item
                for item in hits
                if search_filters.matches(item, years, added_since, added_until)
            )

        # Stop reading once --limit hits are in: results arrive a page at a
        # time, and every page used to be fetched first (Issue #438).
        stop = args.start + args.limit if args.limit and args.limit > 0 else None
        selected = islice(hits, args.start, stop)

        columns = self._COLUMNS + [self._SCORE_COLUMN] if args.fulltext else self._COLUMNS

        def record(item: ZoteroItem) -> dict:
            return self._record(item, scores.get(item.key) if args.fulltext else None)

        if fmt in ("ndjson", "keys"):
            # Written as each result arrives, not after the last page (Issue #556).
            records.render_data(map(record, selected), columns, fmt)
            return

        results = list(selected)

        if fmt != "table":
            records.render_data([record(item) for item in results], columns, fmt)
            return

        if not results:
            console.print("[yellow]No items found.[/yellow]")
            return

        table = Table(title=f"Search Results ({len(results)})")
        table.add_column("Key", style="dim")
        table.add_column("Title")
        table.add_column("Authors")
        table.add_column("Year", justify="right")
        table.add_column("DOI")
        if args.fulltext:
            table.add_column("Score", justify="right")

        for item in results:
            authors = ", ".join(item.authors)
            if len(authors) > 30:
                authors = authors[:27] + "..."

            title = item.title or "Unknown Title"
            display_title = title[:60] + ("..." if len(title) > 60 else "")

            table.add_row(
                item.key,
                safe_markup(display_title),
                safe_markup(authors),
                item.date[:4] if item.date else "N/A",
                item.doi or "",
                *([f"{scores.get(item.key, 0.0):.3g}"] if args.fulltext else []),
            )

        console.print(table)
