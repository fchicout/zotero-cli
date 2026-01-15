import pytest
from unittest.mock import patch, Mock, mock_open
from io import StringIO
import sys
import os
from zotero_cli.cli.main import main

@pytest.fixture(autouse=True)
def mock_config_path(tmp_path):
    # Ensure tests don't load the real ~/.config/zotero-cli/config.toml
    dummy_path = tmp_path / "dummy_config.toml"
    with patch('zotero_cli.core.config.ConfigLoader._get_default_config_path', return_value=dummy_path):
        yield dummy_path

@pytest.fixture
def mock_clients():
    with patch('zotero_cli.infra.factory.GatewayFactory.get_paper_importer') as mock_importer_get, \
         patch('zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway') as mock_zotero_get, \
         patch('zotero_cli.infra.arxiv_lib.ArxivLibGateway') as mock_arxiv, \
         patch('zotero_cli.infra.bibtex_lib.BibtexLibGateway') as mock_bibtex, \
         patch('zotero_cli.infra.ris_lib.RisLibGateway') as mock_ris, \
         patch('zotero_cli.infra.springer_csv_lib.SpringerCsvLibGateway') as mock_springer, \
         patch('zotero_cli.infra.ieee_csv_lib.IeeeCsvLibGateway') as mock_ieee:
        
        mock_importer = mock_importer_get.return_value
        mock_zotero = mock_zotero_get.return_value

        yield {
            'importer': mock_importer,
            'zotero': mock_zotero,
            'arxiv': mock_arxiv.return_value,
            'bibtex': mock_bibtex.return_value,
            'ris': mock_ris.return_value,
            'springer': mock_springer.return_value,
            'ieee': mock_ieee.return_value
        }

@pytest.fixture
def env_vars(monkeypatch):
    monkeypatch.setenv('ZOTERO_API_KEY', 'test_key')
    monkeypatch.setenv('ZOTERO_TARGET_GROUP', 'https://zotero.org/groups/123/name')

# --- 1. SCREEN ---
def test_screen_tui_invocation(mock_clients, env_vars):
    with patch('zotero_cli.cli.commands.screen_cmd.TuiScreeningService') as mock_tui_cls:
        mock_tui = mock_tui_cls.return_value
        test_args = ['zotero-cli', 'screen', '--source', 'S', '--include', 'I', '--exclude', 'E']
        with patch.object(sys, 'argv', test_args):
            main()
        mock_tui.run_screening_session.assert_called_once_with('S', 'I', 'E')

def test_screen_bulk_csv(mock_clients, env_vars, capsys):
    # Mock ScreeningService
    with patch('zotero_cli.cli.commands.screen_cmd.ScreeningService') as mock_service_cls:
        mock_service = mock_service_cls.return_value
        mock_service.record_decision.return_value = True
        
        # Create dummy CSV
        csv_content = "Key,Vote,Reason\nK1,INCLUDE,\nK2,EXCLUDE,bad"
        with patch('builtins.open', mock_open(read_data=csv_content)):
            test_args = ['zotero-cli', 'screen', '--source', 'S', '--include', 'I', '--exclude', 'E', '--file', 'decisions.csv']
            with patch.object(sys, 'argv', test_args):
                main()
        
        captured = capsys.readouterr()
        assert "Processing bulk decisions" in captured.out
        assert "Success: 2, Failed: 0" in captured.out
        assert mock_service.record_decision.call_count == 2

# --- 2. DECIDE ---
def test_decide_cli_invocation(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.commands.screen_cmd.ScreeningService') as mock_screen_cls:
        mock_service = mock_screen_cls.return_value
        mock_service.record_decision.return_value = True
        test_args = [
            'zotero-cli', 'decide', '--key', 'K1', '--vote', 'INCLUDE', 
            '--code', 'IC1'
        ]
        with patch.object(sys, 'argv', test_args):
            main()
        assert "Successfully recorded decision" in capsys.readouterr().out

# --- 3. IMPORT ---
def test_import_manual(mock_clients, env_vars, capsys):
    test_args = ['zotero-cli', 'import', 'manual', '--arxiv-id', '123', '--title', 'T', '--abstract', 'A', '--collection', 'F']
    with patch.object(sys, 'argv', test_args):
        main()
    mock_clients['importer'].add_paper.assert_called_once_with('123', 'A', 'T', 'F')
    assert "Added." in capsys.readouterr().out

def test_import_arxiv(mock_clients, env_vars, capsys):
    mock_clients['importer'].import_with_strategy.return_value = 5
    test_args = ['zotero-cli', 'import', 'arxiv', '--query', 'test query', '--collection', 'F', '--limit', '10']
    with patch.object(sys, 'argv', test_args):
        main()
    
    args, kwargs = mock_clients['importer'].import_with_strategy.call_args
    # args[0] is the strategy
    from zotero_cli.core.strategies import ArxivImportStrategy
    assert isinstance(args[0], ArxivImportStrategy)
    assert args[1] == 'test query'
    assert args[2] == 'F'
    assert kwargs['limit'] == 10
    
    assert "Imported 5 items." in capsys.readouterr().out

def test_import_file_bibtex(mock_clients, env_vars, capsys):
    mock_clients['importer'].import_with_strategy.return_value = 3
    test_args = ['zotero-cli', 'import', 'file', 'papers.bib', '--collection', 'F']
    with patch.object(sys, 'argv', test_args):
        main()
    
    args, _ = mock_clients['importer'].import_with_strategy.call_args
    from zotero_cli.core.strategies import BibtexImportStrategy
    assert isinstance(args[0], BibtexImportStrategy)
    assert args[1] == 'papers.bib'
    assert args[2] == 'F'
    
    assert "Imported 3 items." in capsys.readouterr().out

def test_import_file_csv_ieee(mock_clients, env_vars, capsys):
    mock_clients['importer'].import_with_strategy.return_value = 6
    # Mock open to return IEEE header
    with patch('builtins.open', mock_open(read_data="Document Title,Authors\nPaper 1,Author 1")):
        test_args = ['zotero-cli', 'import', 'file', 'ieee.csv', '--collection', 'F']
        with patch.object(sys, 'argv', test_args):
            main()
    
    args, _ = mock_clients['importer'].import_with_strategy.call_args
    from zotero_cli.core.strategies import IeeeCsvImportStrategy
    assert isinstance(args[0], IeeeCsvImportStrategy)
    assert args[1] == 'ieee.csv'
    assert args[2] == 'F'
    
    assert "Imported 6 items." in capsys.readouterr().out

# --- 4. LIST ---
def test_list_collections(mock_clients, env_vars, capsys):
    mock_clients['zotero'].get_all_collections.return_value = [
        {'key': 'K1', 'data': {'name': 'Col1'}, 'meta': {'numItems': 5}}
    ]
    test_args = ['zotero-cli', 'list', 'collections']
    with patch.object(sys, 'argv', test_args):
        main()
    out = capsys.readouterr().out
    assert "Col1" in out
    assert "K1" in out
    assert "5" in out

def test_list_items(mock_clients, env_vars, capsys):
    mock_item = Mock()
    mock_item.title = "Paper 1"
    mock_item.key = "K1"
    mock_item.item_type = "journalArticle"
    mock_clients['zotero'].get_collection_id_by_name.return_value = "CID"
    mock_clients['zotero'].get_items_in_collection.return_value = iter([mock_item])
    
    test_args = ['zotero-cli', 'list', 'items', '--collection', 'MyCol']
    with patch.object(sys, 'argv', test_args):
        main()
    
    assert "Paper 1" in capsys.readouterr().out
    # We changed the output format to a table, so precise string match might vary
    # But checking for title is safe. Key is now in a separate column.

# --- 5. REPORT ---
def test_report_prisma(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.commands.report_cmd.ReportService') as mock_report_cls:
        mock_service = mock_report_cls.return_value
        mock_report = Mock()
        mock_report.total_items = 10
        mock_report.screened_items = 5
        mock_report.accepted_items = 2
        mock_report.rejected_items = 3
        mock_report.rejections_by_code = {}
        mock_report.malformed_notes = []
        mock_service.generate_prisma_report.return_value = mock_report
        
        test_args = ['zotero-cli', 'report', 'prisma', '--collection', 'MyCol']
        with patch.object(sys, 'argv', test_args):
            main()
        assert "PRISMA Screening Summary" in capsys.readouterr().out

def test_report_snapshot(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.commands.report_cmd.SnapshotService') as mock_snapshot_cls:
        mock_snapshot = mock_snapshot_cls.return_value
        mock_snapshot.freeze_collection.return_value = True
        test_args = ['zotero-cli', 'report', 'snapshot', '--collection', 'MyCol', '--output', 'out.json']
        with patch.object(sys, 'argv', test_args):
            main()
        assert "Snapshot saved" in capsys.readouterr().out

# --- 6. MANAGE ---
def test_manage_tags(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.commands.manage_cmd.TagService') as mock_tag_cls:
        mock_tag = mock_tag_cls.return_value
        mock_tag.list_tags.return_value = ['t1']
        test_args = ['zotero-cli', 'manage', 'tags', 'list']
        with patch.object(sys, 'argv', test_args):
            main()
        assert "t1" in capsys.readouterr().out

def test_manage_pdfs_strip(mock_clients, env_vars, capsys):
    mock_clients['importer'].remove_attachments_from_folder.return_value = 10
    test_args = ['zotero-cli', 'manage', 'pdfs', 'strip', '--collection', 'F']
    with patch.object(sys, 'argv', test_args):
        main()
    assert "Removed 10 attachments" in capsys.readouterr().out

def test_manage_duplicates(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.commands.manage_cmd.DuplicateFinder') as mock_finder_cls:
        mock_finder = mock_finder_cls.return_value
        mock_finder.find_duplicates.return_value = []
        test_args = ['zotero-cli', 'manage', 'duplicates', '--collections', 'A,B']
        with patch.object(sys, 'argv', test_args):
            main()
        assert "No duplicates found" in capsys.readouterr().out

def test_manage_move(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.commands.manage_cmd.CollectionService') as mock_service_cls:
        mock_service = mock_service_cls.return_value
        mock_service.move_item.return_value = True
        test_args = ['zotero-cli', 'manage', 'move', '--item-id', 'I', '--source', 'S', '--target', 'T']
        with patch.object(sys, 'argv', test_args):
            main()
        assert "Moved item I" in capsys.readouterr().out

def test_manage_clean(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.commands.manage_cmd.CollectionService') as mock_service_cls:
        mock_service = mock_service_cls.return_value
        mock_service.empty_collection.return_value = 5
        test_args = ['zotero-cli', 'manage', 'clean', '--collection', 'Trash']
        with patch.object(sys, 'argv', test_args):
            main()
        assert "Deleted 5 items" in capsys.readouterr().out

def test_manage_migrate(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.commands.manage_cmd.MigrationService') as mock_migrate_cls:
        mock_service = mock_migrate_cls.return_value
        mock_service.migrate_collection_notes.return_value = {
            "processed": 10, "migrated": 5, "failed": 0
        }
        test_args = ['zotero-cli', 'manage', 'migrate', '--collection', 'C']
        with patch.object(sys, 'argv', test_args):
            main()
        assert "Processed: 10" in capsys.readouterr().out

# --- 7. ANALYZE ---
def test_analyze_audit(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.commands.analyze_cmd.CollectionAuditor') as mock_auditor_cls:
        mock_auditor = mock_auditor_cls.return_value
        mock_report = Mock()
        mock_report.items_missing_id = []
        mock_report.items_missing_pdf = []
        mock_auditor.audit_collection.return_value = mock_report
        test_args = ['zotero-cli', 'analyze', 'audit', '--collection', 'C']
        with patch.object(sys, 'argv', test_args):
            main()
        assert "Audit Report" in capsys.readouterr().out

def test_analyze_lookup(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.commands.analyze_cmd.LookupService') as mock_lookup_cls:
        mock_lookup = mock_lookup_cls.return_value
        mock_lookup.lookup_items.return_value = "Result"
        test_args = ['zotero-cli', 'analyze', 'lookup', '--keys', 'K1']
        with patch.object(sys, 'argv', test_args):
            main()
        assert "Result" in capsys.readouterr().out

def test_analyze_graph(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.commands.analyze_cmd.CitationGraphService') as mock_graph_cls:
        mock_graph = mock_graph_cls.return_value
        mock_graph.build_graph.return_value = "digraph"
        test_args = ['zotero-cli', 'analyze', 'graph', '--collections', 'C']
        with patch.object(sys, 'argv', test_args):
            main()
        assert "digraph" in capsys.readouterr().out

# --- 8. FIND ---
def test_find_arxiv(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.commands.find_cmd.ArxivQueryParser') as mock_parser_cls:
        mock_parser = mock_parser_cls.return_value
        from zotero_cli.core.services.arxiv_query_parser import ArxivSearchParams
        mock_parser.parse.return_value = ArxivSearchParams(query="parsed", max_results=1)
        mock_clients['arxiv'].search.return_value = iter([Mock(arxiv_id="123", title="Paper 1", year="2023")])
        
        test_args = ['zotero-cli', 'find', 'arxiv', '--query', 'foo']
        with patch.object(sys, 'argv', test_args):
            main()
        out = capsys.readouterr().out
        assert "Paper 1" in out
        assert "2023" in out

# --- CONFIGURATION / MAIN ---

from zotero_cli.core.config import reset_config
from zotero_cli.infra.factory import GatewayFactory

def get_zotero_gateway(*args, **kwargs):
    return GatewayFactory.get_zotero_gateway(*args, **kwargs)

def test_config_group_mode(monkeypatch):
    reset_config()
    monkeypatch.setenv('ZOTERO_API_KEY', 'key')
    monkeypatch.setenv('ZOTERO_TARGET_GROUP', 'https://zotero.org/groups/123')
    
    gw = get_zotero_gateway()
    assert gw.http.library_id == '123'
    assert gw.http.library_type == 'group'

def test_config_user_mode(monkeypatch):
    reset_config()
    monkeypatch.setenv('ZOTERO_API_KEY', 'key')
    monkeypatch.delenv('ZOTERO_TARGET_GROUP', raising=False)
    monkeypatch.setenv('ZOTERO_USER_ID', '999')
    
    gw = get_zotero_gateway()
    assert gw.http.library_id == '999'
    assert gw.http.library_type == 'user'

def test_config_missing_group_id(monkeypatch, capsys):
    reset_config()
    monkeypatch.setenv('ZOTERO_API_KEY', 'key')
    monkeypatch.setenv('ZOTERO_TARGET_GROUP', 'https://bad-url.com')
    
    with pytest.raises(SystemExit):
        get_zotero_gateway()
    assert "Could not extract Group ID" in capsys.readouterr().err

def test_config_no_context(monkeypatch, capsys):
    reset_config()
    monkeypatch.setenv('ZOTERO_API_KEY', 'key')
    monkeypatch.delenv('ZOTERO_TARGET_GROUP', raising=False)
    monkeypatch.delenv('ZOTERO_USER_ID', raising=False)
    
    with pytest.raises(SystemExit):
        get_zotero_gateway()
    assert "No target library defined" in capsys.readouterr().err

def test_config_optional_group(monkeypatch):
    reset_config()
    monkeypatch.setenv('ZOTERO_API_KEY', 'key')
    monkeypatch.delenv('ZOTERO_TARGET_GROUP', raising=False)
    monkeypatch.delenv('ZOTERO_USER_ID', raising=False)
    
    # Should not exit
    gw = get_zotero_gateway(require_group=False)
    assert gw.http.library_id == "0"

