import os
import sqlite3
import tempfile

from zotero_cli.core.services.purge_service import PurgeService
from zotero_cli.infra.sqlite_repo import SqliteZoteroGateway


def setup_mock_db():
    fd, path = tempfile.mkstemp()
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE itemTypes (itemTypeID INTEGER PRIMARY KEY, typeName TEXT);
        CREATE TABLE items (itemID INTEGER PRIMARY KEY, key TEXT, version INTEGER, libraryID INTEGER, itemTypeID INTEGER, parentItemID INTEGER);
        CREATE TABLE fields (fieldID INTEGER PRIMARY KEY, fieldName TEXT);
        CREATE TABLE itemData (itemID INTEGER, fieldID INTEGER, valueID INTEGER);
        CREATE TABLE itemDataValues (valueID INTEGER PRIMARY KEY, value TEXT);
        CREATE TABLE collections (collectionID INTEGER PRIMARY KEY, key TEXT, parentCollection TEXT);
        CREATE TABLE collectionData (collectionID INTEGER, name TEXT);
        CREATE TABLE collectionItems (collectionID INTEGER, itemID INTEGER);
        CREATE TABLE tags (tagID INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE itemTags (itemID INTEGER, tagID INTEGER);
        CREATE TABLE deletedItems (itemID INTEGER PRIMARY KEY);
    """)
    conn.commit()
    conn.close()
    return fd, path

def test_offline_veto_real_object():
    fd, path = setup_mock_db()
    try:
        gateway = SqliteZoteroGateway(path)
        service = PurgeService(gateway)

        print("Testing Offline Veto for purge_attachments...")
        try:
            service.purge_attachments(["K1"])
            print("FAILED: Did not raise RuntimeError")
            exit(1)
        except RuntimeError as e:
            print(f"PASSED: {e}")

        print("Testing Offline Veto for purge_notes...")
        try:
            service.purge_notes(["K1"])
            print("FAILED: Did not raise RuntimeError")
            exit(1)
        except RuntimeError as e:
            print(f"PASSED: {e}")

        print("Testing Offline Veto for purge_tags...")
        try:
            service.purge_tags(["K1"])
            print("FAILED: Did not raise RuntimeError")
            exit(1)
        except RuntimeError as e:
            print(f"PASSED: {e}")

    finally:
        os.close(fd)
        if os.path.exists(path):
            os.remove(path)

if __name__ == "__main__":
    test_offline_veto_real_object()
