import json
import re
from typing import Dict

from zotero_cli.core.interfaces import ZoteroGateway


class MigrationService:
    """
    Service for migrating and cleaning up Zotero notes metadata.
    Specifically handles the transition from legacy formats to SDB v1.1.
    """

    def __init__(self, gateway: ZoteroGateway):
        self.gateway = gateway

    def migrate_collection_notes(self, collection_name: str, dry_run: bool = True) -> Dict[str, int]:
        """
        Iterates over items in a collection and cleans up their screening notes.
        """
        col_id = self.gateway.get_collection_id_by_name(collection_name)
        if not col_id:
            return {"error": 1}

        items = self.gateway.get_items_in_collection(col_id)
        stats = {"processed": 0, "migrated": 0, "already_clean": 0, "failed": 0}

        for item in items:
            stats["processed"] += 1
            children = self.gateway.get_item_children(item.key)

            for child in children:
                # Handle different API response structures
                child_data = child.get('data', child)
                if child_data.get('itemType') == 'note':
                    note_key = child['key']
                    note_version = child_data.get('version', 0)
                    note_content = child_data.get('note', '')

                    if self._is_screening_note(note_content):
                        new_content = self._migrate_note_content(note_content)
                        if new_content != note_content:
                            if not dry_run:
                                success = self.gateway.update_note(note_key, note_version, new_content)
                                if success:
                                    stats["migrated"] += 1
                                else:
                                    stats["failed"] += 1
                            else:
                                stats["migrated"] += 1
                        else:
                            stats["already_clean"] += 1

        return stats

    def _is_screening_note(self, content: str) -> bool:
        return 'screening_decision' in content or 'audit_version' in content or '"signature":' in content or '"decision":' in content

    def _migrate_note_content(self, content: str) -> str:
        """
        Parses JSON from note, removes 'signature', standardizes 'agent',
        and ensures 'audit_version' 1.1.
        """
        # Extract JSON
        match = re.search(r'(\{.*\})', content, re.DOTALL)
        if not match:
            return content

        try:
            data = json.loads(match.group(1))
            changed = False

            # 1. Remove 'signature'
            if 'signature' in data:
                del data['signature']
                changed = True

            # 2. Standardize 'agent'
            if data.get('agent') != 'zotero-cli':
                # If agent was something else but it's a tool decision, standardize.
                # If it was a persona name in agent, move it to persona if missing.
                if data.get('agent') and data.get('agent') not in ['zotero-cli', 'zotero-cli-tui', 'zotero-cli-agent']:
                    if not data.get('persona') or data.get('persona') == 'unknown':
                        data['persona'] = data['agent']
                    data['agent'] = 'zotero-cli'
                elif not data.get('agent'):
                    data['agent'] = 'zotero-cli'
                changed = True

            # 3. Ensure audit_version 1.1
            if data.get('audit_version') != '1.1':
                data['audit_version'] = '1.1'
                changed = True

            # 4. Handle legacy 'code' vs 'reason_code'
            if 'code' in data and 'reason_code' not in data:
                data['reason_code'] = [data['code']]
                del data['code']
                changed = True
            elif 'reason_code' in data and isinstance(data['reason_code'], str):
                data['reason_code'] = [c.strip() for c in data['reason_code'].split(',')]
                changed = True

            if changed:
                return f"<div>{json.dumps(data, indent=2)}</div>"
            else:
                return content

        except json.JSONDecodeError:
            return content
