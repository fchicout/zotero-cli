import pytest
from unittest.mock import patch, Mock, mock_open
from io import StringIO
import sys
import os
from zotero_cli.cli.main import main
from zotero_cli.client import CollectionNotFoundError

@pytest.fixture
def mock_clients():
    with patch('zotero_cli.cli.main.PaperImporterClient') as mock_importer, \
         patch('zotero_cli.cli.main.ZoteroAPIClient') as mock_zotero, \
         patch('zotero_cli.cli.main.ArxivLibGateway') as mock_arxiv, \
         patch('zotero_cli.cli.main.BibtexLibGateway') as mock_bibtex, \
         patch('zotero_cli.cli.main.RisLibGateway') as mock_ris, \
         patch('zotero_cli.cli.main.SpringerCsvLibGateway') as mock_springer, \
         patch('zotero_cli.cli.main.IeeeCsvLibGateway') as mock_ieee:
        
        yield {
            'importer': mock_importer.return_value,
            'zotero': mock_zotero.return_value,
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

def test_add_command_success(mock_clients, env_vars, capsys):
    test_args = ['zotero-cli', 'add', '--arxiv-id', '123', '--title', 'T', '--abstract', 'A', '--folder', 'F']
    with patch.object(sys, 'argv', test_args):
        main()
    
    mock_clients['importer'].add_paper.assert_called_once_with('123', 'A', 'T', 'F')
    captured = capsys.readouterr()
    assert "Successfully added" in captured.out

def test_import_command_success(mock_clients, env_vars, capsys):
    mock_clients['importer'].import_from_query.return_value = 5
    test_args = ['zotero-cli', 'import', '--query', 'test query', '--folder', 'F', '--limit', '10']
    with patch.object(sys, 'argv', test_args):
        main()
    
    mock_clients['importer'].import_from_query.assert_called_once_with(
        'test query', 'F', 10, False, 'relevance', 'descending'
    )
    captured = capsys.readouterr()
    assert "Successfully imported 5 papers" in captured.out

def test_bibtex_command_success(mock_clients, env_vars, capsys):
    mock_clients['importer'].import_from_bibtex.return_value = 3
    test_args = ['zotero-cli', 'bibtex', '--file', 'papers.bib', '--folder', 'F']
    with patch.object(sys, 'argv', test_args):
        main()
    
    mock_clients['importer'].import_from_bibtex.assert_called_once_with('papers.bib', 'F', False)
    captured = capsys.readouterr()
    assert "Successfully imported 3 papers" in captured.out

def test_ris_command_success(mock_clients, env_vars, capsys):
    mock_clients['importer'].import_from_ris.return_value = 4
    test_args = ['zotero-cli', 'ris', '--file', 'papers.ris', '--folder', 'F']
    with patch.object(sys, 'argv', test_args):
        main()
    
    mock_clients['importer'].import_from_ris.assert_called_once_with('papers.ris', 'F', False)
    captured = capsys.readouterr()
    assert "Successfully imported 4 papers" in captured.out

def test_ieee_csv_command_success(mock_clients, env_vars, capsys):
    mock_clients['importer'].import_from_ieee_csv.return_value = 6
    test_args = ['zotero-cli', 'ieee-csv', '--file', 'ieee.csv', '--folder', 'F']
    with patch.object(sys, 'argv', test_args):
        main()
    
    mock_clients['importer'].import_from_ieee_csv.assert_called_once_with('ieee.csv', 'F', False)
    captured = capsys.readouterr()
    assert "Successfully imported 6 papers" in captured.out

def test_remove_attachments_command_success(mock_clients, env_vars, capsys):
    mock_clients['importer'].remove_attachments_from_folder.return_value = 10
    test_args = ['zotero-cli', 'remove-attachments', '--folder', 'F']
    with patch.object(sys, 'argv', test_args):
        main()
    
    mock_clients['importer'].remove_attachments_from_folder.assert_called_once_with('F', False)
    captured = capsys.readouterr()
    assert "Successfully deleted 10 attachments" in captured.out

def test_import_command_file_input(mock_clients, env_vars):
    mock_clients['importer'].import_from_query.return_value = 1
    file_content = "query from file"
    with patch('builtins.open', mock_open(read_data=file_content)):
        test_args = ['zotero-cli', 'import', '--file', 'query.txt', '--folder', 'F']
        with patch.object(sys, 'argv', test_args):
            main()
    
    mock_clients['importer'].import_from_query.assert_called_once_with(
        'query from file', 'F', 100, False, 'relevance', 'descending'
    )

def test_import_command_pipe_input(mock_clients, env_vars):
    mock_clients['importer'].import_from_query.return_value = 1
    test_args = ['zotero-cli', 'import', '--folder', 'F']
    with patch.object(sys, 'argv', test_args):
        with patch('sys.stdin', StringIO('query from pipe')):
            with patch('sys.stdin.isatty', return_value=False):
                main()
    
    mock_clients['importer'].import_from_query.assert_called_once_with(
        'query from pipe', 'F', 100, False, 'relevance', 'descending'
    )

def test_import_command_structured_query(mock_clients, env_vars, capsys):
    mock_clients['importer'].import_from_query.return_value = 1
    # Trigger DSL parsing with ; and :
    structured_query = "terms: title=AI; size: 10"
    test_args = ['zotero-cli', 'import', '--query', structured_query, '--folder', 'F']
    with patch.object(sys, 'argv', test_args):
        main()
    
    # Verify it was parsed (title=AI becomes title:(AI) in parser)
    mock_clients['importer'].import_from_query.assert_called_once_with(
        'title:(AI)', 'F', 10, False, 'relevance', 'descending'
    )

def test_import_command_no_query(mock_clients, env_vars, capsys):
    test_args = ['zotero-cli', 'import', '--folder', 'F']
    with patch.object(sys, 'argv', test_args):
        with patch('sys.stdin.isatty', return_value=True): 
            with pytest.raises(SystemExit) as e:
                main()
            assert e.value.code == 1
    
    captured = capsys.readouterr()
    assert "Error: No query provided" in captured.err

def test_missing_api_key_fails(monkeypatch, capsys):
    monkeypatch.delenv('ZOTERO_API_KEY', raising=False)
    test_args = ['zotero-cli', 'list-collections']
    with patch.object(sys, 'argv', test_args):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1
    captured = capsys.readouterr()
    assert "Error: ZOTERO_API_KEY environment variable not set" in captured.err

def test_invalid_group_url_fails(monkeypatch, capsys):
    monkeypatch.setenv('ZOTERO_API_KEY', 'test_key')
    monkeypatch.setenv('ZOTERO_TARGET_GROUP', 'invalid_url')
    test_args = ['zotero-cli', 'list-collections']
    with patch.object(sys, 'argv', test_args):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1
    captured = capsys.readouterr()
    assert "Error: Could not extract Group ID" in captured.err

def test_move_command_failure(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.main.CollectionService') as mock_service_cls:
        mock_service = mock_service_cls.return_value
        mock_service.move_item.return_value = False
        test_args = ['zotero-cli', 'move', '--id', 'ID', '--from-col', 'A', '--to-col', 'B']
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit) as e:
                main()
            assert e.value.code == 1
        assert "Failed to move item" in capsys.readouterr().out

def test_audit_command_failure(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.main.CollectionAuditor') as mock_auditor_cls:
        mock_auditor = mock_auditor_cls.return_value
        mock_auditor.audit_collection.return_value = None # Failure
        test_args = ['zotero-cli', 'audit', '--collection', 'MyCol']
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit) as e:
                main()
            assert e.value.code == 1

def test_no_subcommand_prints_help(mock_clients, env_vars, capsys):
    test_args = ['zotero-cli']
    with patch.object(sys, 'argv', test_args):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1
    captured = capsys.readouterr()
    assert "usage: zotero-cli" in captured.out

def test_move_command_success(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.main.CollectionService') as mock_service_cls:
        mock_service = mock_service_cls.return_value
        mock_service.move_item.return_value = True
        test_args = ['zotero-cli', 'move', '--id', 'DOI123', '--from-col', 'A', '--to-col', 'B']
        with patch.object(sys, 'argv', test_args):
            main()
        mock_service.move_item.assert_called_once_with('A', 'B', 'DOI123')
        assert "Successfully moved" in capsys.readouterr().out

def test_audit_command_success(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.main.CollectionAuditor') as mock_auditor_cls:
        mock_auditor = mock_auditor_cls.return_value
        mock_report = Mock()
        mock_report.total_items = 10
        mock_report.items_missing_id = []
        mock_report.items_missing_title = []
        mock_report.items_missing_abstract = []
        mock_report.items_missing_pdf = []
        mock_auditor.audit_collection.return_value = mock_report
        
        test_args = ['zotero-cli', 'audit', '--collection', 'MyCol']
        with patch.object(sys, 'argv', test_args):
            main()
        
        mock_auditor.audit_collection.assert_called_once_with('MyCol')
        assert "Audit Report for collection 'MyCol'" in capsys.readouterr().out

def test_duplicates_command_success(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.main.DuplicateFinder') as mock_finder_cls:
        mock_finder = mock_finder_cls.return_value
        mock_finder.find_duplicates.return_value = [] # No duplicates
        test_args = ['zotero-cli', 'duplicates', '--collections', 'A, B']
        with patch.object(sys, 'argv', test_args):
            main()
        mock_finder.find_duplicates.assert_called_once_with(['A', 'B'])
        assert "No duplicate items found" in capsys.readouterr().out

def test_graph_command_success(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.main.CitationGraphService') as mock_graph_cls:
        mock_graph = mock_graph_cls.return_value
        mock_graph.build_graph.return_value = "digraph {}"
        test_args = ['zotero-cli', 'graph', '--collections', 'A, B']
        with patch.object(sys, 'argv', test_args):
            main()
        mock_graph.build_graph.assert_called_once_with(['A', 'B'])
        assert "digraph {}" in capsys.readouterr().out

def test_tag_list_success(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.main.TagService') as mock_tag_cls:
        mock_tag = mock_tag_cls.return_value
        mock_tag.list_tags.return_value = ['tag1', 'tag2']
        test_args = ['zotero-cli', 'tag', 'list']
        with patch.object(sys, 'argv', test_args):
            main()
        assert "tag1" in capsys.readouterr().out

def test_tag_rename_success(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.main.TagService') as mock_tag_cls:
        mock_tag = mock_tag_cls.return_value
        mock_tag.rename_tag.return_value = 5
        test_args = ['zotero-cli', 'tag', 'rename', '--old', 'A', '--new', 'B']
        with patch.object(sys, 'argv', test_args):
            main()
        mock_tag.rename_tag.assert_called_once_with('A', 'B')
        assert "Renamed tag 'A' to 'B' on 5 items" in capsys.readouterr().out

def test_tag_delete_success(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.main.TagService') as mock_tag_cls:
        mock_tag = mock_tag_cls.return_value
        mock_tag.delete_tag.return_value = 1
        test_args = ['zotero-cli', 'tag', 'delete', '--tag', 'old_tag']
        with patch.object(sys, 'argv', test_args):
            main()
        mock_tag.delete_tag.assert_called_once_with('old_tag')
        assert "Deleted tag 'old_tag'" in capsys.readouterr().out

def test_tag_add_success(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.main.TagService') as mock_tag_cls:
        mock_tag = mock_tag_cls.return_value
        mock_item = Mock()
        mock_item.key = "ITEM1"
        mock_clients['zotero'].get_item.return_value = mock_item
        test_args = ['zotero-cli', 'tag', 'add', '--item', 'ITEM1', '--tags', 't1,t2']
        with patch.object(sys, 'argv', test_args):
            main()
        mock_tag.add_tags_to_item.assert_called_once_with('ITEM1', mock_item, ['t1', 't2'])
        assert "Successfully added to item 'ITEM1'" in capsys.readouterr().out

def test_empty_collection_success(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.main.CollectionService') as mock_service_cls:
        mock_service = mock_service_cls.return_value
        mock_service.empty_collection.return_value = 5
        test_args = ['zotero-cli', 'empty-collection', '--collection', 'Trash']
        with patch.object(sys, 'argv', test_args):
            main()
        mock_service.empty_collection.assert_called_once_with('Trash', None, False)
        assert "Deleted 5 items from collection 'Trash'" in capsys.readouterr().out

def test_springer_csv_command_success(mock_clients, env_vars, capsys):
    mock_clients['importer'].import_from_springer_csv.return_value = 2
    test_args = ['zotero-cli', 'springer-csv', '--file', 'springer.csv', '--folder', 'F']
    with patch.object(sys, 'argv', test_args):
        main()
    mock_clients['importer'].import_from_springer_csv.assert_called_once_with('springer.csv', 'F', False)
    assert "Successfully imported 2 papers" in capsys.readouterr().out

def test_attach_pdf_command_success(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.main.AttachmentService') as mock_attach_cls:
        mock_attachment = mock_attach_cls.return_value
        mock_attachment.attach_pdfs_to_collection.return_value = 3
        test_args = ['zotero-cli', 'attach-pdf', '--collection', 'MyCol']
        with patch.object(sys, 'argv', test_args):
            main()
        mock_attachment.attach_pdfs_to_collection.assert_called_once_with('MyCol')
        assert "Attached 3 PDFs" in capsys.readouterr().out

def test_list_collections_command_success(mock_clients, env_vars, capsys):
    mock_clients['zotero'].get_all_collections.return_value = [
        {'key': 'K1', 'data': {'name': 'Col1'}, 'meta': {'numItems': 5}}
    ]
    test_args = ['zotero-cli', 'list-collections']
    with patch.object(sys, 'argv', test_args):
        main()
    assert "Col1 (Key: K1, Items: 5)" in capsys.readouterr().out

def test_search_arxiv_command_success(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.main.ArxivQueryParser') as mock_parser_cls:
        mock_parser = mock_parser_cls.return_value
        from zotero_cli.core.services.arxiv_query_parser import ArxivSearchParams
        mock_parser.parse.return_value = ArxivSearchParams(query="parsed query", max_results=1)
        mock_clients['arxiv'].search.return_value = iter([Mock(title="Paper 1", year="2023")])
        test_args = ['zotero-cli', 'search-arxiv', '--query', 'raw query']
        with patch.object(sys, 'argv', test_args):
            main()
        assert "Paper 1 (2023)" in capsys.readouterr().out

def test_freeze_command_success(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.main.SnapshotService') as mock_snapshot_cls:
        mock_snapshot = mock_snapshot_cls.return_value
        mock_snapshot.freeze_collection.return_value = True
        test_args = ['zotero-cli', 'freeze', '--collection', 'MyCol', '--output', 'out.json']
        with patch.object(sys, 'argv', test_args):
            main()
        assert "Successfully froze collection" in capsys.readouterr().out

def test_lookup_command_success(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.main.LookupService') as mock_lookup_cls:
        mock_lookup = mock_lookup_cls.return_value
        mock_lookup.lookup_items.return_value = "Lookup Result"
        test_args = ['zotero-cli', 'lookup', '--keys', 'K1,K2']
        with patch.object(sys, 'argv', test_args):
            main()
        assert "Lookup Result" in capsys.readouterr().out

def test_report_command_success(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.main.ReportService') as mock_report_cls:
        mock_service = mock_report_cls.return_value
        mock_report = Mock()
        mock_report.collection_name = "MyCol"
        mock_report.total_items = 10
        mock_report.screened_items = 5
        mock_report.accepted_items = 2
        mock_report.rejected_items = 3
        mock_report.rejections_by_code = {"EC1": 3}
        mock_report.malformed_notes = []
        mock_service.generate_prisma_report.return_value = mock_report
        
        test_args = ['zotero-cli', 'report', '--collection', 'MyCol']
        with patch.object(sys, 'argv', test_args):
            main()
        assert "PRISMA Screening Summary" in capsys.readouterr().out

def test_decision_command_success(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.main.ScreeningService') as mock_screen_cls:
        mock_service = mock_screen_cls.return_value
        mock_service.record_decision.return_value = True
        test_args = ['zotero-cli', 'decision', '--key', 'K1', '--vote', 'INCLUDE', '--code', 'IC1']
        with patch.object(sys, 'argv', test_args):
            main()
        assert "Successfully recorded decision" in capsys.readouterr().out

def test_migrate_command_success(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.main.MigrationService') as mock_migrate_cls:
        mock_service = mock_migrate_cls.return_value
        mock_service.migrate_collection_notes.return_value = {
            "processed": 10, "migrated": 5, "already_clean": 5, "failed": 0
        }
        test_args = ['zotero-cli', 'migrate', '--collection', 'MyCol']
        with patch.object(sys, 'argv', test_args):
            main()
        assert "Migration Results" in capsys.readouterr().out

def test_screen_command_success(mock_clients, env_vars):
    with patch('zotero_cli.cli.main.TuiScreeningService') as mock_tui_cls:
        mock_tui = mock_tui_cls.return_value
        test_args = ['zotero-cli', 'screen', '--source', 'S', '--include', 'I', '--exclude', 'E']
        with patch.object(sys, 'argv', test_args):
            main()
        mock_tui.run_screening_session.assert_called_once_with('S', 'I', 'E')
        
def test_search_arxiv_file_input(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.main.ArxivQueryParser') as mock_parser_cls:
        mock_parser = mock_parser_cls.return_value
        from zotero_cli.core.services.arxiv_query_parser import ArxivSearchParams
        mock_parser.parse.return_value = ArxivSearchParams(query="parsed", max_results=1)
        mock_clients['arxiv'].search.return_value = iter([])
        
        with patch('builtins.open', mock_open(read_data="query from file")):
            test_args = ['zotero-cli', 'search-arxiv', '--file', 'q.txt', '--verbose']
            with patch.object(sys, 'argv', test_args):
                main()
        assert "Parsed Parameters" in capsys.readouterr().out
        
def test_lookup_command_file_input(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.main.LookupService') as mock_lookup_cls:
        mock_lookup = mock_lookup_cls.return_value
        mock_lookup.lookup_items.return_value = "Result"
        
        with patch('builtins.open', mock_open(read_data="K1\nK2")):
            test_args = ['zotero-cli', 'lookup', '--file', 'keys.txt']
            with patch.object(sys, 'argv', test_args):
                main()
        assert "Result" in capsys.readouterr().out
        
def test_report_command_full_options(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.main.ReportService') as mock_report_cls:
        mock_service = mock_report_cls.return_value
        mock_report = Mock()
        mock_report.total_items = 1
        mock_report.screened_items = 1
        mock_report.accepted_items = 1
        mock_report.rejected_items = 0
        mock_report.rejections_by_code = {}
        mock_report.malformed_notes = ["MAL1"]
        mock_service.generate_prisma_report.return_value = mock_report
        mock_service.generate_mermaid_prisma.return_value = "mermaid code"
        mock_service.render_diagram.return_value = True
        
        test_args = ['zotero-cli', 'report', '--collection', 'C', '--verbose', '--output-chart', 'p.png']
        with patch.object(sys, 'argv', test_args):
            main()
        
        captured = capsys.readouterr()
        assert "Malformed note" in captured.out
        assert "Diagram successfully saved" in captured.out
        
def test_decision_command_full_options(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.main.ScreeningService') as mock_screen_cls:
        mock_service = mock_screen_cls.return_value
        mock_service.record_decision.return_value = True
        test_args = [
            'zotero-cli', 'decision', '--key', 'K1', '--vote', 'EXCLUDE', 
            '--code', 'EC1', '--reason', 'R', '--source', 'S', '--target', 'T', 
            '--agent-led', '--persona', 'Alice', '--phase', 'full_text'
        ]
        with patch.object(sys, 'argv', test_args):
            main()
        
        mock_service.record_decision.assert_called_once_with(
            item_key='K1', decision='EXCLUDE', code='EC1', reason='R',
            source_collection='S', target_collection='T',
            agent='zotero-cli-agent', persona='Alice', phase='full_text'
        )

def test_migrate_command_dry_run(mock_clients, env_vars, capsys):
    with patch('zotero_cli.cli.main.MigrationService') as mock_migrate_cls:
        mock_service = mock_migrate_cls.return_value
        mock_service.migrate_collection_notes.return_value = {
            "processed": 1, "migrated": 1, "already_clean": 0, "failed": 0
        }
        test_args = ['zotero-cli', 'migrate', '--collection', 'C', '--dry-run']
        with patch.object(sys, 'argv', test_args):
            main()
        assert "Note: This was a DRY RUN" in capsys.readouterr().out