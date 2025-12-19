"""Unit tests for CLI argument parsing.

This module tests the command-line interface argument parsing logic,
including required arguments, default values, and flag handling.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from bibtools.cli.main import main, execute_pipeline


class TestCLIArgumentParsing:
    """Test suite for CLI argument parsing."""
    
    def test_required_input_argument_missing(self):
        """Test that missing --input argument causes parser error."""
        # Simulate command line without --input
        test_args = ['prog']
        
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            # argparse exits with code 2 for argument errors
            assert exc_info.value.code == 2
    
    def test_required_input_argument_provided(self, tmp_path):
        """Test that --input argument is correctly parsed."""
        # Create a temporary CSV file
        test_csv = tmp_path / "test.csv"
        test_csv.write_text("Item Title,Authors,Publication Year\n", encoding='utf-8')
        
        test_args = ['prog', 'convert', '--input', str(test_csv)]
        
        with patch.object(sys, 'argv', test_args):
            with patch('custom.cli.main.execute_pipeline') as mock_execute:
                mock_execute.return_value = 0
                
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                # Should exit with code 0 (success)
                assert exc_info.value.code == 0
                
                # Verify execute_pipeline was called with correct input path
                mock_execute.assert_called_once()
                call_args = mock_execute.call_args[0]
                assert call_args[0] == Path(str(test_csv))
    
    def test_default_output_dir(self, tmp_path):
        """Test that --output-dir defaults to 'data/output'."""
        # Create a temporary CSV file
        test_csv = tmp_path / "test.csv"
        test_csv.write_text("Item Title,Authors,Publication Year\n", encoding='utf-8')
        
        test_args = ['prog', 'convert', '--input', str(test_csv)]
        
        with patch.object(sys, 'argv', test_args):
            with patch('custom.cli.main.execute_pipeline') as mock_execute:
                mock_execute.return_value = 0
                
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                assert exc_info.value.code == 0
                
                # Verify default output directory
                call_args = mock_execute.call_args[0]
                assert call_args[1] == Path('data/output')
    
    def test_custom_output_dir(self, tmp_path):
        """Test that --output-dir can be customized."""
        # Create a temporary CSV file
        test_csv = tmp_path / "test.csv"
        test_csv.write_text("Item Title,Authors,Publication Year\n", encoding='utf-8')
        
        custom_output = tmp_path / "custom_output"
        test_args = ['prog', 'convert', '--input', str(test_csv), '--output-dir', str(custom_output)]
        
        with patch.object(sys, 'argv', test_args):
            with patch('custom.cli.main.execute_pipeline') as mock_execute:
                mock_execute.return_value = 0
                
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                assert exc_info.value.code == 0
                
                # Verify custom output directory
                call_args = mock_execute.call_args[0]
                assert call_args[1] == Path(str(custom_output))
    
    def test_fix_authors_flag_default_false(self, tmp_path):
        """Test that --fix-authors flag defaults to False."""
        # Create a temporary CSV file
        test_csv = tmp_path / "test.csv"
        test_csv.write_text("Item Title,Authors,Publication Year\n", encoding='utf-8')
        
        test_args = ['prog', 'convert', '--input', str(test_csv)]
        
        with patch.object(sys, 'argv', test_args):
            with patch('custom.cli.main.execute_pipeline') as mock_execute:
                mock_execute.return_value = 0
                
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                assert exc_info.value.code == 0
                
                # Verify fix_authors is False by default
                call_args = mock_execute.call_args[0]
                assert call_args[2] is False
    
    def test_fix_authors_flag_enabled(self, tmp_path):
        """Test that --fix-authors flag can be enabled."""
        # Create a temporary CSV file
        test_csv = tmp_path / "test.csv"
        test_csv.write_text("Item Title,Authors,Publication Year\n", encoding='utf-8')
        
        test_args = ['prog', 'convert', '--input', str(test_csv), '--fix-authors']
        
        with patch.object(sys, 'argv', test_args):
            with patch('custom.cli.main.execute_pipeline') as mock_execute:
                mock_execute.return_value = 0
                
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                assert exc_info.value.code == 0
                
                # Verify fix_authors is True
                call_args = mock_execute.call_args[0]
                assert call_args[2] is True
    
    def test_nonexistent_input_file(self, tmp_path):
        """Test that nonexistent input file causes error."""
        nonexistent_file = tmp_path / "nonexistent.csv"
        test_args = ['prog', 'convert', '--input', str(nonexistent_file)]
        
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            # Should exit with code 1 (error)
            assert exc_info.value.code == 1
    
    def test_input_path_is_directory(self, tmp_path):
        """Test that providing a directory as input causes error."""
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()
        
        test_args = ['prog', 'convert', '--input', str(test_dir)]
        
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            # Should exit with code 1 (error)
            assert exc_info.value.code == 1
    
    def test_all_arguments_together(self, tmp_path):
        """Test all arguments provided together."""
        # Create a temporary CSV file
        test_csv = tmp_path / "test.csv"
        test_csv.write_text("Item Title,Authors,Publication Year\n", encoding='utf-8')
        
        custom_output = tmp_path / "output"
        test_args = [
            'prog',
            'convert',
            '--input', str(test_csv),
            '--output-dir', str(custom_output),
            '--fix-authors'
        ]
        
        with patch.object(sys, 'argv', test_args):
            with patch('custom.cli.main.execute_pipeline') as mock_execute:
                mock_execute.return_value = 0
                
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                assert exc_info.value.code == 0
                
                # Verify all arguments
                call_args = mock_execute.call_args[0]
                assert call_args[0] == Path(str(test_csv))
                assert call_args[1] == Path(str(custom_output))
                assert call_args[2] is True


class TestExecutePipeline:
    """Test suite for execute_pipeline function."""
    
    def test_execute_pipeline_conversion_only(self, tmp_path):
        """Test pipeline execution without author fixing."""
        # Create test input file
        test_csv = tmp_path / "test.csv"
        test_csv.write_text(
            "Item Title,Authors,Publication Year,Item DOI,URL,Publication Title\n"
            "Test Article,John Smith,2023,10.1234/test,http://example.com,Test Journal\n",
            encoding='utf-8'
        )
        
        output_dir = tmp_path / "output"
        
        with patch('custom.cli.main.CSVConverter') as mock_converter_class:
            # Mock the converter instance and its convert method
            mock_converter = MagicMock()
            mock_converter_class.return_value = mock_converter
            
            # Mock successful conversion result
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.entries_count = 1
            mock_result.output_files = [output_dir / "springer_results_raw_part1.bib"]
            mock_result.errors = []
            mock_converter.convert.return_value = mock_result
            
            exit_code = execute_pipeline(test_csv, output_dir, fix_authors=False)
            
            assert exit_code == 0
            mock_converter.convert.assert_called_once_with(test_csv, output_dir, output_base_name="springer_results_raw")
    
    def test_execute_pipeline_with_author_fixing(self, tmp_path):
        """Test pipeline execution with author fixing enabled."""
        # Create test input file
        test_csv = tmp_path / "test.csv"
        test_csv.write_text(
            "Item Title,Authors,Publication Year,Item DOI,URL,Publication Title\n"
            "Test Article,John Smith,2023,10.1234/test,http://example.com,Test Journal\n",
            encoding='utf-8'
        )
        
        output_dir = tmp_path / "output"
        raw_file = output_dir / "springer_results_raw_part1.bib"
        
        with patch('custom.cli.main.CSVConverter') as mock_converter_class, \
             patch('custom.cli.main.AuthorFixer') as mock_fixer_class:
            
            # Mock converter
            mock_converter = MagicMock()
            mock_converter_class.return_value = mock_converter
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.entries_count = 1
            mock_result.output_files = [raw_file]
            mock_result.errors = []
            mock_converter.convert.return_value = mock_result
            
            # Mock fixer
            mock_fixer = MagicMock()
            mock_fixer_class.return_value = mock_fixer
            mock_fix_result = MagicMock()
            mock_fix_result.success = True
            mock_fix_result.entries_count = 1
            mock_fix_result.errors = []
            mock_fixer.fix_file.return_value = mock_fix_result
            
            exit_code = execute_pipeline(test_csv, output_dir, fix_authors=True)
            
            assert exit_code == 0
            mock_converter.convert.assert_called_once()
            mock_fixer.fix_file.assert_called_once()
    
    def test_execute_pipeline_conversion_failure(self, tmp_path):
        """Test pipeline handles conversion failure."""
        test_csv = tmp_path / "test.csv"
        test_csv.write_text("Item Title,Authors\n", encoding='utf-8')
        
        output_dir = tmp_path / "output"
        
        with patch('custom.cli.main.CSVConverter') as mock_converter_class:
            mock_converter = MagicMock()
            mock_converter_class.return_value = mock_converter
            
            # Mock failed conversion
            mock_result = MagicMock()
            mock_result.success = False
            mock_result.errors = ["Conversion error"]
            mock_converter.convert.return_value = mock_result
            
            exit_code = execute_pipeline(test_csv, output_dir, fix_authors=False)
            
            assert exit_code == 1
    
    def test_execute_pipeline_conversion_exception(self, tmp_path):
        """Test pipeline handles conversion exception."""
        test_csv = tmp_path / "test.csv"
        test_csv.write_text("Item Title,Authors\n", encoding='utf-8')
        
        output_dir = tmp_path / "output"
        
        with patch('custom.cli.main.CSVConverter') as mock_converter_class:
            mock_converter = MagicMock()
            mock_converter_class.return_value = mock_converter
            mock_converter.convert.side_effect = Exception("Test exception")
            
            exit_code = execute_pipeline(test_csv, output_dir, fix_authors=False)
            
            assert exit_code == 1
