import os
import sys
# Add the directory containing zotero_cli (src) to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from zotero_cli.infra.zotero_api import ZoteroAPIClient

def list_collections():
    api_key = os.environ.get("ZOTERO_API_KEY")
    library_id = os.environ.get("ZOTERO_LIBRARY_ID")
    
    if not api_key or not library_id:
        print("Error: ZOTERO_API_KEY and ZOTERO_LIBRARY_ID must be set.")
        sys.exit(1)

    client = ZoteroAPIClient(api_key, library_id)
    
    try:
        # Fetch top-level collections
        collections = client.get_all_collections()
        print(f"Found {len(collections)} collections.")
        for col in collections:
            data = col.get('data', {})
            name = data.get('name', 'Unknown')
            key = col.get('key')
            parent = data.get('parentCollection', 'None')
            print(f"Name: {name}, Key: {key}, Parent: {parent}")
    except Exception as e:
        print(f"Error fetching collections: {e}")

if __name__ == "__main__":
    list_collections()