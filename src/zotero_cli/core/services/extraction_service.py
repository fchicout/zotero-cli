import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from zotero_cli.core.interfaces import NoteRepository

# Valid types as per SDB-Extraction v1.0
VALID_TYPES = {"text", "number", "boolean", "select", "multi-select", "date"}


class ExtractionSchemaValidator:
    """
    Helper class for managing and validating the SLR Extraction Schema.
    """

    def __init__(self, schema_path: str = "schema.yaml"):
        self.schema_path = schema_path

    def init_schema(self) -> bool:
        if os.path.exists(self.schema_path):
            return False

        current_dir = Path(__file__).parent.parent.parent
        template_path = current_dir / "templates" / "extraction_schema.yaml"

        if not template_path.exists():
            raise FileNotFoundError(f"Template not found at {template_path}")

        shutil.copy(template_path, self.schema_path)
        return True

    def load_schema(self) -> Dict[str, Any]:
        if not os.path.exists(self.schema_path):
            raise FileNotFoundError(f"Schema file not found: {self.schema_path}")

        with open(self.schema_path, "r", encoding="utf-8") as f:
            try:
                return yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML format: {e}")

    def validate(self) -> List[str]:
        errors = []
        try:
            data = self.load_schema()
        except (FileNotFoundError, ValueError) as e:
            return [str(e)]

        if not data.get("title"):
            errors.append("Missing required top-level field: 'title'")
        if not data.get("version"):
            errors.append("Missing required top-level field: 'version'")

        variables = data.get("variables")
        if not variables:
            errors.append("Missing or empty 'variables' list.")
            return errors

        if not isinstance(variables, list):
            errors.append("'variables' must be a list.")
            return errors

        seen_keys = set()
        for idx, var in enumerate(variables):
            if not isinstance(var, dict):
                errors.append(f"Variable #{idx+1} is not a dictionary.")
                continue

            key = var.get("key")
            if not key:
                errors.append(f"Variable #{idx+1} missing 'key'.")
            else:
                if key in seen_keys:
                    errors.append(f"Duplicate key found: '{key}'.")
                seen_keys.add(key)
                if not key.islower() or " " in key:
                    errors.append(f"Key '{key}' should be snake_case (lowercase, no spaces).")

            if not var.get("label"):
                errors.append(f"Variable '{key or ('#' + str(idx+1))}' missing 'label'.")

            v_type = var.get("type")
            if not v_type:
                errors.append(f"Variable '{key or ('#' + str(idx+1))}' missing 'type'.")
            elif v_type not in VALID_TYPES:
                errors.append(
                    f"Variable '{key}' has invalid type '{v_type}'. Must be one of: {', '.join(VALID_TYPES)}"
                )

            if v_type in ("select", "multi-select"):
                options = var.get("options")
                if not options or not isinstance(options, list) or len(options) == 0:
                    errors.append(
                        f"Variable '{key}' of type '{v_type}' must have a non-empty 'options' list."
                    )

        return errors


class ExtractionService:
    """
    Core service for Data Extraction.
    Handles Schema Validation and Persistence (Note Saving).
    """

    def __init__(self, note_repo: NoteRepository, schema_path: str = "schema.yaml"):
        self.note_repo = note_repo
        self.validator = ExtractionSchemaValidator(schema_path)

    def save_extraction(
        self,
        item_key: str,
        data: Dict[str, Any],
        schema_version: str,
        agent: str = "zotero-cli",
        persona: str = "unknown",
    ) -> bool:
        """
        Saves extracted data as a Zotero Note (SDB-Extraction format).
        Updates existing note if found for the same persona.
        """
        # 1. Prepare Payload
        payload = {
            "sdb_version": "1.2",
            "action": "data_extraction",
            "phase": "extraction",
            "persona": persona,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "schema_version": schema_version,
            "data": data,
        }
        note_content = f"<div>{json.dumps(payload, indent=2)}</div>"

        # 2. Check for existing note
        children = self.note_repo.get_item_children(item_key)
        existing_note_key: Optional[str] = None
        existing_version: int = 0

        for child in children:
            child_data = child.get("data", child)
            if child_data.get("itemType") == "note":
                content = child_data.get("note", "")
                if (
                    '"action": "data_extraction"' in content
                    and f'"persona": "{persona}"' in content
                ):
                    existing_note_key = child.get("key") or child_data.get("key")
                    existing_version = int(
                        child.get("version") or child_data.get("version") or 0
                    )
                    break

        # 3. Save
        if existing_note_key:
            return self.note_repo.update_note(existing_note_key, existing_version, note_content)
        else:
            return self.note_repo.create_note(item_key, note_content)

    def export_matrix(
        self,
        items: List[Any],
        output_format: str = "csv",
        persona: str = "unknown",
        output_path: Optional[str] = None,
    ) -> str:
        """
        Exports extraction data for a list of items into a synthesis matrix.
        """
        # 1. Load Schema for headers
        schema = self.validator.load_schema()
        variables = schema.get("variables", [])
        var_labels = [v["label"] for v in variables]

        headers = ["Item Key", "Title", "Year"] + var_labels
        matrix_data = []

        for item in items:
            row = {
                "Item Key": item.key,
                "Title": item.title,
                "Year": item.date or "",
            }

            # Find extraction note
            children = self.note_repo.get_item_children(item.key)
            extracted_values = {}

            for child in children:
                child_data = child.get("data", child)
                if child_data.get("itemType") == "note":
                    content = child_data.get("note", "")
                    if (
                        '"action": "data_extraction"' in content
                        and f'"persona": "{persona}"' in content
                    ):
                        try:
                            # Extract JSON from <div>...</div>
                            json_str = content.strip()
                            if json_str.startswith("<div>"):
                                json_str = json_str[5:]
                            if json_str.endswith("</div>"):
                                json_str = json_str[:-6]

                            note_payload = json.loads(json_str)
                            extracted_values = note_payload.get("data", {})
                            break
                        except Exception:
                            continue

            # Map extracted values to row
            for var in variables:
                key = var["key"]
                label = var["label"]
                val_obj = extracted_values.get(key, {})
                val = val_obj.get("value", "")

                # Format multi-select or lists
                if isinstance(val, list):
                    val = "; ".join(map(str, val))

                row[label] = val

            matrix_data.append(row)

        # 2. Format Output
        if output_format == "json":
            result = json.dumps(matrix_data, indent=2)
            ext = "json"
        elif output_format == "markdown":
            result = self._format_markdown_table(headers, matrix_data)
            ext = "md"
        else:  # csv
            result = self._format_csv(headers, matrix_data)
            ext = "csv"

        # 3. Save to file
        final_path = output_path or f"synthesis_matrix.{ext}"
        with open(final_path, "w", encoding="utf-8") as f:
            f.write(result)

        return final_path

    def _format_csv(self, headers: List[str], data: List[Dict[str, Any]]) -> str:
        import csv
        import io

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        for row in data:
            writer.writerow(row)
        return output.getvalue()

    def _format_markdown_table(self, headers: List[str], data: List[Dict[str, Any]]) -> str:
        lines = []
        # Header
        lines.append("| " + " | ".join(headers) + " |")
        # Separator
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        # Rows
        for row in data:
            row_vals = [str(row.get(h, "")) for h in headers]
            lines.append("| " + " | ".join(row_vals) + " |")
        return "\n".join(lines)

