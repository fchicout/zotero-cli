import os
import shutil
from typing import Any, Dict, List, Optional
import yaml
from pathlib import Path

# Valid types as per SDB-Extraction v1.0
VALID_TYPES = {"text", "number", "boolean", "select", "multi-select", "date"}

class ExtractionSchemaValidator:
    """
    Service responsible for managing and validating the SLR Extraction Schema.
    """

    def __init__(self, schema_path: str = "schema.yaml"):
        self.schema_path = schema_path

    def init_schema(self) -> bool:
        """
        Initializes a new schema.yaml from the internal template.
        Returns True if successful, False if file already exists.
        """
        if os.path.exists(self.schema_path):
            return False

        # Locate template
        # Assuming src/zotero_cli/templates/extraction_schema.yaml
        # This relative path calculation depends on where this file is installed.
        # A safer way in a package is usually importlib.resources, but for this CLI structure:
        current_dir = Path(__file__).parent.parent.parent # zotero_cli/core/services -> zotero_cli/
        template_path = current_dir / "templates" / "extraction_schema.yaml"

        if not template_path.exists():
             # Fallback for dev environment or weird packaging
             # Try to find it relative to cwd if we are running from source root? 
             # No, let's rely on the package structure.
             raise FileNotFoundError(f"Template not found at {template_path}")

        shutil.copy(template_path, self.schema_path)
        return True

    def load_schema(self) -> Dict[str, Any]:
        """Loads the schema file safely."""
        if not os.path.exists(self.schema_path):
            raise FileNotFoundError(f"Schema file not found: {self.schema_path}")
        
        with open(self.schema_path, "r", encoding="utf-8") as f:
            try:
                return yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML format: {e}")

    def validate(self) -> List[str]:
        """
        Validates the schema against SDB-Extraction v1.0 rules.
        Returns a list of error messages. Empty list means valid.
        """
        errors = []
        try:
            data = self.load_schema()
        except (FileNotFoundError, ValueError) as e:
            return [str(e)]

        # Top-level checks
        if not data.get("title"):
            errors.append("Missing required top-level field: 'title'")
        if not data.get("version"):
            errors.append("Missing required top-level field: 'version'")
        
        variables = data.get("variables")
        if not variables:
            errors.append("Missing or empty 'variables' list.")
            return errors # Cannot validate items if list is missing

        if not isinstance(variables, list):
            errors.append("'variables' must be a list.")
            return errors

        # Item-level checks
        seen_keys = set()
        for idx, var in enumerate(variables):
            if not isinstance(var, dict):
                errors.append(f"Variable #{idx+1} is not a dictionary.")
                continue

            # 1. Key validation
            key = var.get("key")
            if not key:
                errors.append(f"Variable #{idx+1} missing 'key'.")
            else:
                if key in seen_keys:
                    errors.append(f"Duplicate key found: '{key}'.")
                seen_keys.add(key)
                # Check snake_case (optional but recommended by spec)
                if not key.islower() or " " in key:
                    errors.append(f"Key '{key}' should be snake_case (lowercase, no spaces).")

            # 2. Label validation
            if not var.get("label"):
                errors.append(f"Variable '{key or ('#' + str(idx+1))}' missing 'label'.")

            # 3. Type validation
            v_type = var.get("type")
            if not v_type:
                errors.append(f"Variable '{key or ('#' + str(idx+1))}' missing 'type'.")
            elif v_type not in VALID_TYPES:
                errors.append(f"Variable '{key}' has invalid type '{v_type}'. Must be one of: {', '.join(VALID_TYPES)}")
            
            # 4. Options validation (for select types)
            if v_type in ("select", "multi-select"):
                options = var.get("options")
                if not options or not isinstance(options, list) or len(options) == 0:
                    errors.append(f"Variable '{key}' of type '{v_type}' must have a non-empty 'options' list.")

        return errors
