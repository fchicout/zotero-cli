import os
import pytest
import yaml
from zotero_cli.core.services.extraction_service import ExtractionSchemaValidator

class TestExtractionSchemaValidator:

    def test_init_schema(self, tmp_path):
        target_file = tmp_path / "new_schema.yaml"
        validator = ExtractionSchemaValidator(str(target_file))
        
        # Test 1: Successful Init
        # We rely on the actual template file existing in the source tree.
        # If this fails in CI, we might need to mock the template path, 
        # but for this environment, it should work.
        result = validator.init_schema()
        assert result is True
        assert target_file.exists()
        
        # Verify content briefly
        with open(target_file) as f:
            content = f.read()
            assert "SLR Extraction Protocol Template" in content

        # Test 2: File exists (Should fail)
        result_exists = validator.init_schema()
        assert result_exists is False

    def test_load_schema_errors(self, tmp_path):
        # Test 1: File Not Found
        validator = ExtractionSchemaValidator(str(tmp_path / "non_existent.yaml"))
        with pytest.raises(FileNotFoundError):
            validator.load_schema()
            
        # Test 2: Invalid YAML
        bad_yaml = tmp_path / "bad.yaml"
        with open(bad_yaml, "w") as f:
            f.write("key: : value") # Invalid YAML syntax
        
        validator = ExtractionSchemaValidator(str(bad_yaml))
        with pytest.raises(ValueError) as excinfo:
            validator.load_schema()
        assert "Invalid YAML format" in str(excinfo.value)

    def test_validate_valid_schema(self, tmp_path):
        schema_file = tmp_path / "schema.yaml"
        data = {
            "title": "Test Schema",
            "version": "1.0",
            "variables": [
                {"key": "v1", "label": "V1", "type": "text"},
                {"key": "v2", "label": "V2", "type": "select", "options": ["A", "B"]}
            ]
        }
        with open(schema_file, "w") as f:
            yaml.dump(data, f)
            
        validator = ExtractionSchemaValidator(str(schema_file))
        errors = validator.validate()
        assert len(errors) == 0

    def test_validate_missing_fields(self, tmp_path):
        schema_file = tmp_path / "schema.yaml"
        data = {"title": "Test"} # Missing version and variables
        with open(schema_file, "w") as f:
            yaml.dump(data, f)
            
        validator = ExtractionSchemaValidator(str(schema_file))
        errors = validator.validate()
        assert any("missing required top-level field: 'version'" in e.lower() for e in errors)
        assert any("missing or empty 'variables'" in e.lower() for e in errors)

    def test_validate_invalid_variable(self, tmp_path):
        schema_file = tmp_path / "schema.yaml"
        data = {
            "title": "Test",
            "version": "1.0",
            "variables": [
                {"label": "No Key", "type": "text"}, # Missing key
                {"key": "Bad Type", "label": "L", "type": "magic"}, # Bad type, space in key
                {"key": "sel", "label": "S", "type": "select"} # Missing options
            ]
        }
        with open(schema_file, "w") as f:
            yaml.dump(data, f)
            
        validator = ExtractionSchemaValidator(str(schema_file))
        errors = validator.validate()
        
        assert any("missing 'key'" in e.lower() for e in errors)
        assert any("snake_case" in e.lower() for e in errors)
        assert any("invalid type 'magic'" in e.lower() for e in errors)
        assert any("must have a non-empty 'options'" in e.lower() for e in errors)
