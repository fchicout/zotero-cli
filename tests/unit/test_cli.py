import sys
from unittest.mock import Mock, mock_open, patch

import pytest

from zotero_cli.cli.main import main
from zotero_cli.core.config import reset_config
from zotero_cli.infra.factory import GatewayFactory


@pytest.fixture(autouse=True)
def mock_config_path(tmp_path):
    # Ensure tests don't load the real ~/.config/zotero-cli/config.toml
    dummy_path = tmp_path / "dummy_config.toml"
    with patch(
        "zotero_cli.core.config.ConfigLoader._get_default_config_path", return_value=dummy_path
    ):
        yield dummy_path


@pytest.fixture
def mock_clients():
    with (
        patch("zotero_cli.infra.factory.GatewayFactory.get_import_service") as mock_importer_get,
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_zotero_get,
        patch("zotero_cli.infra.factory.GatewayFactory.get_arxiv_gateway") as mock_arxiv,
        patch("zotero_cli.infra.factory.GatewayFactory.get_bibtex_gateway") as mock_bibtex,
        patch("zotero_cli.infra.factory.GatewayFactory.get_ris_gateway") as mock_ris,
        patch("zotero_cli.infra.factory.GatewayFactory.get_springer_csv_gateway") as mock_springer,
        patch("zotero_cli.infra.factory.GatewayFactory.get_ieee_csv_gateway") as mock_ieee,
        patch("zotero_cli.infra.factory.GatewayFactory.get_canonical_csv_gateway") as mock_canon,
    ):
        mock_importer = mock_importer_get.return_value
        mock_zotero = mock_zotero_get.return_value

        yield {
            "importer": mock_importer,
            "zotero": mock_zotero,
            "arxiv": mock_arxiv.return_value,
            "bibtex": mock_bibtex.return_value,
            "ris": mock_ris.return_value,
            "springer": mock_springer.return_value,
            "ieee": mock_ieee.return_value,
            "canon": mock_canon.return_value,
        }


@pytest.fixture
def env_vars(monkeypatch):
    monkeypatch.setenv("ZOTERO_API_KEY", "test_key")
    monkeypatch.setenv("ZOTERO_USER_ID", "12345")
    monkeypatch.setenv("ZOTERO_TARGET_GROUP", "https://zotero.org/groups/123/name")


# --- 1. SCREEN ---
def test_screen_tui_invocation(mock_clients, env_vars):
    with patch("zotero_cli.cli.commands.slr_cmd.TuiScreeningService") as mock_tui_cls:
        mock_tui = mock_tui_cls.return_value
        test_args = [
            "zotero-cli",
            "slr",
            "screen",
            "--source",
            "S",
            "--include",
            "I",
            "--exclude",
            "E",
        ]
        with patch.object(sys, "argv", test_args):
            main()
        mock_tui.run_screening_session.assert_called_once_with("S", "I", "E")


def test_screen_bulk_csv(mock_clients, env_vars, capsys):
    # Mock ScreeningService via Factory
    with patch("zotero_cli.infra.factory.GatewayFactory.get_screening_service") as mock_factory_get:
        mock_service = mock_factory_get.return_value
        mock_service.record_decision.return_value = True

        # Create dummy CSV
        csv_content = "Key,Vote,Reason\nK1,INCLUDE,\nK2,EXCLUDE,bad"
        with patch("builtins.open", mock_open(read_data=csv_content)):
            test_args = [
                "zotero-cli",
                "slr",
                "screen",
                "--source",
                "S",
                "--include",
                "I",
                "--exclude",
                "E",
                "--file",
                "decisions.csv",
            ]
            with patch.object(sys, "argv", test_args):
                main()

        captured = capsys.readouterr()
        assert "Processing bulk decisions" in captured.out
        assert "Success: 2, Failed: 0" in captured.out
        assert mock_service.record_decision.call_count == 2


# --- 2. DECIDE ---
def test_decide_cli_invocation(mock_clients, env_vars, capsys):
    with patch("zotero_cli.infra.factory.GatewayFactory.get_screening_service") as mock_factory_get:
        mock_service = mock_factory_get.return_value
        mock_service.record_decision.return_value = True
        test_args = [
            "zotero-cli",
            "slr",
            "decide",
            "--key",
            "K1",
            "--vote",
            "INCLUDE",
            "--code",
            "IC1",
        ]
        with patch.object(sys, "argv", test_args):
            main()
        assert "Successfully recorded decision" in capsys.readouterr().out


def test_decide_include_no_code(mock_clients, env_vars, capsys):
    with patch("zotero_cli.infra.factory.GatewayFactory.get_screening_service") as mock_factory_get:
        mock_service = mock_factory_get.return_value
        mock_service.record_decision.return_value = True
        test_args = [
            "zotero-cli",
            "slr",
            "decide",
            "--key",
            "K1",
            "--vote",
            "INCLUDE",
        ]
        with patch.object(sys, "argv", test_args):
            main()
        
        # Should succeed without --code
        assert "Successfully recorded decision" in capsys.readouterr().out
        # Verify service called with code=None (or empty string depending on impl, 
        # but the command passes the arg directly)
        call_args = mock_service.record_decision.call_args[1]
        assert call_args["decision"] == "INCLUDE"


def test_decide_exclude_requires_code(mock_clients, env_vars, capsys):
    test_args = [
        "zotero-cli",
        "slr",
        "decide",
        "--key",
        "K1",
        "--vote",
        "EXCLUDE",
    ]
    with patch.object(sys, "argv", test_args):
        with pytest.raises(SystemExit):
            main()
    
    assert "Error: You must provide --code for EXCLUDE decisions." in capsys.readouterr().out


# --- 3. IMPORT ---
def test_import_manual(mock_clients, env_vars, capsys):
    test_args = [
        "zotero-cli",
        "import",
        "manual",
        "--arxiv-id",
        "123",
        "--title",
        "T",
        "--abstract",
        "A",
        "--collection",
        "F",
    ]
    with patch.object(sys, "argv", test_args):
        main()
    # Check manual paper call
    args, _ = mock_clients["importer"].add_manual_paper.call_args
    assert args[0].arxiv_id == "123"
    assert args[0].title == "T"
    assert args[1] == "F"
    assert "Added." in capsys.readouterr().out


def test_import_arxiv(mock_clients, env_vars, capsys):
    mock_clients["importer"].import_papers.return_value = 5
    test_args = [
        "zotero-cli",
        "import",
        "arxiv",
        "--query",
        "test query",
        "--collection",
        "F",
        "--limit",
        "10",
    ]
    with patch.object(sys, "argv", test_args):
        main()

    # In refactored ImportCommand, ImportService.import_papers is called
    assert mock_clients["importer"].import_papers.called
    args, _ = mock_clients["importer"].import_papers.call_args
    assert args[1] == "F"

    assert "Imported 5 items." in capsys.readouterr().out


def test_import_file_bibtex(mock_clients, env_vars, capsys):
    mock_clients["importer"].import_papers.return_value = 3
    test_args = ["zotero-cli", "import", "file", "papers.bib", "--collection", "F"]
    with patch.object(sys, "argv", test_args):
        main()

    assert mock_clients["importer"].import_papers.called
    args, _ = mock_clients["importer"].import_papers.call_args
    assert args[1] == "F"

    assert "Imported 3 items." in capsys.readouterr().out


def test_import_file_csv_ieee(mock_clients, env_vars, capsys):
    mock_clients["importer"].import_papers.return_value = 6
    # Mock open to return IEEE header
    with patch("builtins.open", mock_open(read_data="Document Title,Authors\nPaper 1,Author 1")):
        test_args = ["zotero-cli", "import", "file", "ieee.csv", "--collection", "F"]
        with patch.object(sys, "argv", test_args):
            main()

    assert mock_clients["importer"].import_papers.called
    args, _ = mock_clients["importer"].import_papers.call_args
    assert args[1] == "F"

    assert "Imported 6 items." in capsys.readouterr().out


# --- 4. LIST ---
def test_list_collections(mock_clients, env_vars, capsys):
    mock_clients["zotero"].get_all_collections.return_value = [
        {"key": "K1", "data": {"name": "Col1"}, "meta": {"numItems": 5}}
    ]
    test_args = ["zotero-cli", "list", "collections"]
    with patch.object(sys, "argv", test_args):
        main()
    out = capsys.readouterr().out
    assert "Col1" in out
    assert "K1" in out
    assert "5" in out


def test_list_groups(mock_clients, env_vars, capsys):
    mock_clients["zotero"].get_user_groups.return_value = [
        {"id": 123, "data": {"name": "Research Group"}, "url": "..."}
    ]
    test_args = ["zotero-cli", "list", "groups"]
    with patch.object(sys, "argv", test_args):
        main()
    out = capsys.readouterr().out
    assert "123" in out
    assert "Research Group" in out


def test_list_items(mock_clients, env_vars, capsys):
    mock_item = Mock()
    mock_item.title = "Paper 1"
    mock_item.key = "K1"
    mock_item.item_type = "journalArticle"
    mock_clients["zotero"].get_collection_id_by_name.return_value = "CID"
    mock_clients["zotero"].get_items_in_collection.return_value = iter([mock_item])

    test_args = ["zotero-cli", "list", "items", "--collection", "MyCol"]
    with patch.object(sys, "argv", test_args):
        main()

    assert "Paper 1" in capsys.readouterr().out
    # We changed the output format to a table, so precise string match might vary
    # But checking for title is safe. Key is now in a separate column.


def test_list_items_not_found(mock_clients, env_vars, capsys):
    mock_clients["zotero"].get_collection_id_by_name.return_value = None

    test_args = ["zotero-cli", "list", "items", "--collection", "NonExistent"]
    with patch.object(sys, "argv", test_args):
        main()

    # It currently prints an empty table if not found, but it should ideally error.
    # For now, let's just assert it shows 0 items.
    assert "Showing 0 items" in capsys.readouterr().out


def test_list_items_top_only(mock_clients, env_vars, capsys):
    mock_item = Mock()
    mock_item.title = "Paper Top"
    mock_item.key = "K_TOP"
    mock_item.item_type = "journalArticle"
    mock_clients["zotero"].get_collection_id_by_name.return_value = "CID"
    mock_clients["zotero"].get_items_in_collection.return_value = iter([mock_item])

    test_args = ["zotero-cli", "list", "items", "--collection", "MyCol", "--top-only"]
    with patch.object(sys, "argv", test_args):
        main()

    # Verify the call to gateway includes top_only=True
    mock_clients["zotero"].get_items_in_collection.assert_called_once_with("CID", top_only=True)
    assert "Paper Top" in capsys.readouterr().out


# --- 5. REPORT ---
def test_report_prisma(mock_clients, env_vars, capsys):
    with patch("zotero_cli.cli.commands.report_cmd.ReportService") as mock_report_cls:
        mock_service = mock_report_cls.return_value
        mock_report = Mock()
        mock_report.total_items = 10
        mock_report.screened_items = 5
        mock_report.accepted_items = 2
        mock_report.rejected_items = 3
        mock_report.rejections_by_code = {}
        mock_report.malformed_notes = []
        mock_service.generate_prisma_report.return_value = mock_report

        test_args = ["zotero-cli", "report", "prisma", "--collection", "MyCol"]
        with patch.object(sys, "argv", test_args):
            main()
        assert "PRISMA Screening Summary" in capsys.readouterr().out


def test_report_snapshot(mock_clients, env_vars, capsys):
    with patch("zotero_cli.cli.commands.report_cmd.SnapshotService") as mock_snapshot_cls:
        mock_snapshot = mock_snapshot_cls.return_value
        mock_snapshot.freeze_collection.return_value = True
        test_args = [
            "zotero-cli",
            "report",
            "snapshot",
            "--collection",
            "MyCol",
            "--output",
            "out.json",
        ]
        with patch.object(sys, "argv", test_args):
            main()
        assert "Snapshot saved" in capsys.readouterr().out


def test_report_screening(mock_clients, env_vars, capsys, tmp_path):
    with patch("zotero_cli.cli.commands.report_cmd.ReportService") as mock_report_cls:
        mock_service = mock_report_cls.return_value
        mock_report = Mock()
        mock_report.collection_name = "MyCol"
        mock_service.generate_prisma_report.return_value = mock_report
        mock_service.generate_screening_markdown.return_value = "# Report Content"

        out_file = tmp_path / "report.md"
        test_args = [
            "zotero-cli",
            "report",
            "screening",
            "--collection",
            "MyCol",
            "--output",
            str(out_file),
        ]
        with patch.object(sys, "argv", test_args):
            main()

        assert "Screening report saved" in capsys.readouterr().out
        assert out_file.exists()
        assert out_file.read_text() == "# Report Content"


def test_report_status(mock_clients, env_vars, capsys, tmp_path):
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway"):
        with patch("zotero_cli.cli.commands.report_cmd.ReportService") as mock_report_cls:
            mock_service = mock_report_cls.return_value
            mock_report = Mock()
            mock_report.collection_name = "MyCol"
            mock_service.generate_prisma_report.return_value = mock_report
            mock_service.generate_screening_markdown.return_value = "# Dashboard Content"

            out_file = tmp_path / "status.md"
            test_args = [
                "zotero-cli",
                "report",
                "status",
                "--collection",
                "MyCol",
                "--output",
                str(out_file),
            ]
            with patch.object(sys, "argv", test_args):
                main()

            assert "Screening report saved" in capsys.readouterr().out
            assert out_file.exists()
            assert out_file.read_text() == "# Dashboard Content"


# --- 6. TAG ---
def test_tag_list(mock_clients, env_vars, capsys):
    mock_clients["zotero"].get_tags.return_value = ["t1"]
    test_args = ["zotero-cli", "tag", "list"]
    with patch.object(sys, "argv", test_args):
        main()
    assert "t1" in capsys.readouterr().out


# --- 7. COLLECTION ---
    def test_collection_pdfs_strip(mock_clients, env_vars, capsys):
        with patch("zotero_cli.infra.factory.GatewayFactory.get_attachment_service") as mock_att_get:
            mock_att = mock_att_get.return_value
            mock_att.remove_attachments_from_collection.return_value = 10
            test_args = ["zotero-cli", "collection", "pdf", "strip", "--collection", "F"]
            with patch.object(sys, "argv", test_args):
                main()
            assert "Would remove 10 attachments" in capsys.readouterr().out

def test_collection_duplicates(mock_clients, env_vars, capsys):
    with patch("zotero_cli.core.services.duplicate_service.DuplicateFinder") as mock_finder_cls:
        mock_finder = mock_finder_cls.return_value
        mock_finder.find_duplicates.return_value = []
        test_args = ["zotero-cli", "collection", "duplicates", "--collections", "A,B"]
        with patch.object(sys, "argv", test_args):
            main()
        assert "No duplicates found" in capsys.readouterr().out


def test_collection_clean(mock_clients, env_vars, capsys):
    with patch(
        "zotero_cli.infra.factory.GatewayFactory.get_collection_service"
    ) as mock_factory_get:
        mock_service = mock_factory_get.return_value
        mock_service.empty_collection.return_value = 5
        test_args = ["zotero-cli", "collection", "clean", "--collection", "Trash"]
        with patch.object(sys, "argv", test_args):
            main()
        assert "Deleted 5 items" in capsys.readouterr().out


# --- 8. ITEM ---
def test_item_move(mock_clients, env_vars, capsys):
    with patch(
        "zotero_cli.infra.factory.GatewayFactory.get_collection_service"
    ) as mock_factory_get:
        mock_service = mock_factory_get.return_value
        mock_service.move_item.return_value = True
        test_args = [
            "zotero-cli",
            "item",
            "move",
            "--item-id",
            "I",
            "--source",
            "S",
            "--target",
            "T",
        ]
        with patch.object(sys, "argv", test_args):
            main()
        assert "Moved item I" in capsys.readouterr().out


# --- 9. REVIEW ---
def test_review_migrate(mock_clients, env_vars, capsys):
    with patch("zotero_cli.cli.commands.slr_cmd.MigrationService") as mock_migrate_cls:
        mock_migrate = mock_migrate_cls.return_value
        mock_migrate.migrate_collection_notes.return_value = {
            "processed": 1,
            "migrated": 1,
            "failed": 0,
        }
        test_args = ["zotero-cli", "slr", "migrate", "--collection", "C"]
        with patch.object(sys, "argv", test_args):
            main()
        assert "Migration results for C" in capsys.readouterr().out


# --- 7. ANALYZE ---
def test_audit_check(mock_clients, env_vars, capsys):
    with patch("zotero_cli.cli.commands.slr_cmd.CollectionAuditor") as mock_auditor_cls:
        mock_auditor = mock_auditor_cls.return_value
        mock_report = Mock()
        mock_report.total_items = 0
        mock_report.items_missing_id = []
        mock_report.items_missing_title = []
        mock_report.items_missing_abstract = []
        mock_report.items_missing_pdf = []
        mock_report.items_missing_note = []
        mock_auditor.audit_collection.return_value = mock_report
        test_args = ["zotero-cli", "slr", "validate", "--collection", "C"]
        with patch.object(sys, "argv", test_args):
            main()
        assert "Auditing collection: C" in capsys.readouterr().out


def test_analyze_lookup(mock_clients, env_vars, capsys):
    with patch("zotero_cli.cli.commands.slr_cmd.LookupService") as mock_lookup_cls:
        mock_lookup = mock_lookup_cls.return_value
        mock_lookup.lookup_items.return_value = "Lookup Result"
        test_args = ["zotero-cli", "slr", "lookup", "--keys", "K1"]
        with patch.object(sys, "argv", test_args):
            main()
        assert "Lookup Result" in capsys.readouterr().out


def test_analyze_graph(mock_clients, env_vars, capsys):
    with patch("zotero_cli.cli.commands.slr_cmd.CitationGraphService") as mock_graph_cls:
        mock_graph = mock_graph_cls.return_value
        mock_graph.build_graph.return_value = "digraph {}"
        test_args = ["zotero-cli", "slr", "graph", "--collections", "C"]
        with patch.object(sys, "argv", test_args):
            main()
        assert "digraph {}" in capsys.readouterr().out


# --- 8. FIND ---
def test_find_arxiv(mock_clients, env_vars, capsys):
    with patch("zotero_cli.cli.commands.import_cmd.ArxivQueryParser") as mock_parser_cls:
        mock_parser = mock_parser_cls.return_value
        from zotero_cli.core.services.arxiv_query_parser import ArxivSearchParams

        mock_parser.parse.return_value = ArxivSearchParams(
            query="parsed", max_results=1, sort_by="relevance", sort_order="descending"
        )

        # Configure the importer mock to return a count
        mock_clients["importer"].import_papers.return_value = 1

        test_args = ["zotero-cli", "import", "arxiv", "--query", "foo", "--collection", "F"]
        with patch.object(sys, "argv", test_args):
            main()

        out = capsys.readouterr().out
        assert "Imported 1 items" in out
        mock_clients["importer"].import_papers.assert_called_once()


# --- CONFIGURATION / MAIN ---


def get_zotero_gateway(*args, **kwargs):
    return GatewayFactory.get_zotero_gateway(*args, **kwargs)


def test_config_group_mode(monkeypatch):
    reset_config()
    monkeypatch.setenv("ZOTERO_API_KEY", "key")
    monkeypatch.setenv("ZOTERO_TARGET_GROUP", "https://zotero.org/groups/123")

    gw = get_zotero_gateway()
    assert gw.http.library_id == "123"
    assert gw.http.library_type == "group"


def test_config_user_mode(monkeypatch):
    reset_config()
    monkeypatch.setenv("ZOTERO_API_KEY", "key")
    monkeypatch.delenv("ZOTERO_TARGET_GROUP", raising=False)
    monkeypatch.setenv("ZOTERO_USER_ID", "999")

    gw = get_zotero_gateway()
    assert gw.http.library_id == "999"
    assert gw.http.library_type == "user"


def test_config_missing_group_id(monkeypatch, capsys):
    reset_config()
    monkeypatch.setenv("ZOTERO_API_KEY", "key")
    monkeypatch.setenv("ZOTERO_TARGET_GROUP", "https://bad-url.com")

    with pytest.raises(SystemExit):
        get_zotero_gateway()
    assert "Could not extract Group ID" in capsys.readouterr().err


def test_config_no_context(monkeypatch, capsys):
    reset_config()
    monkeypatch.setenv("ZOTERO_API_KEY", "key")
    monkeypatch.delenv("ZOTERO_TARGET_GROUP", raising=False)
    monkeypatch.delenv("ZOTERO_USER_ID", raising=False)

    with pytest.raises(SystemExit):
        get_zotero_gateway()
    assert "No target library defined" in capsys.readouterr().err


def test_config_optional_group(monkeypatch):
    reset_config()
    monkeypatch.setenv("ZOTERO_API_KEY", "key")
    monkeypatch.delenv("ZOTERO_TARGET_GROUP", raising=False)
    monkeypatch.delenv("ZOTERO_USER_ID", raising=False)

    # Should not exit
    gw = get_zotero_gateway(require_group=False)
    assert gw.http.library_id == "0"


def test_item_move_auto_source(mock_clients, env_vars, capsys):
    with patch(
        "zotero_cli.infra.factory.GatewayFactory.get_collection_service"
    ) as mock_factory_get:
        mock_service = mock_factory_get.return_value

        mock_service.move_item.return_value = True

        # Source not provided

        test_args = ["zotero-cli", "item", "move", "--item-id", "I", "--target", "T"]

        with patch.object(sys, "argv", test_args):
            main()

        # Verify call arguments

        # Argument order in CollectionService.move_item(source, target, item_id)

        mock_service.move_item.assert_called_once_with(None, "T", "I")

        assert "Moved item I" in capsys.readouterr().out
