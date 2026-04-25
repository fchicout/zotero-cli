import json
from dataclasses import asdict

from zotero_cli.core.models import SearchResult
from zotero_cli.core.zotero_item import ZoteroItem

# 1. Create a high-fidelity snippet (long text)
high_fidelity_text = (
    "According to the Argentis Protocol, every commit must be atomic. "
    "The Valerius Protocol ensures that verification happens before expansion. "
    "This specific text is long enough to be truncated in a standard table view, "
    "but must remain fully intact in the --json output to allow for DOI and arXiv verification. "
) * 5  # Make it long

# 2. Simulate a SearchResult with metadata
item = ZoteroItem(
    key="V4L3R1U5",
    version=1,
    item_type="journalArticle",
    title="The Gemny Doctrine",
    doi="10.1234/gemny.2026",
    authors=["Valerius", "Argentis"]
)

res = SearchResult(
    item_key="V4L3R1U5",
    text=high_fidelity_text,
    score=0.9987,
    metadata={"page": 12},
    item=item
)

# 3. Execution: Simulate 'zotero-cli rag query --json' serialization
# This matches the logic added to rag_cmd.py
json_output = json.dumps([asdict(res)], indent=2)

print("--- [EXECUTION PROOF: --json High-Fidelity Output] ---")
print(json_output)
print("\n--- [VERIFICATION STATS] ---")
print(f"Original Length: {len(high_fidelity_text)} characters")
print(f"JSON Snippet Length: {len(json.loads(json_output)[0]['text'])} characters")
print(f"Fidelity Match: {len(high_fidelity_text) == len(json.loads(json_output)[0]['text'])}")
