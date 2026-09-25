"""
Offline self-test of the installed program (Issue #403): checks that the
features which depend on bundled libraries actually work, not only that
they import. The release workflow runs it against every built binary.
"""

import base64
import os
import sqlite3
import tempfile
from dataclasses import dataclass
from typing import List

# A one-page PDF (Helvetica text) - small enough to embed, so the check needs
# no data file in the binary.
SAMPLE_PDF_TEXT = "zotero-cli selftest: PDF text extraction works"
SAMPLE_PDF = base64.b64decode(
    "JVBERi0xLjQKMSAwIG9iago8PCAvVHlwZSAvQ2F0YWxvZyAvUGFnZXMgMiAwIFIgPj4KZW5kb2Jq"
    "CjIgMCBvYmoKPDwgL1R5cGUgL1BhZ2VzIC9LaWRzIFszIDAgUl0gL0NvdW50IDEgPj4KZW5kb2Jq"
    "CjMgMCBvYmoKPDwgL1R5cGUgL1BhZ2UgL1BhcmVudCAyIDAgUiAvTWVkaWFCb3ggWzAgMCA2MTIg"
    "NzkyXSAvUmVzb3VyY2VzIDw8IC9Gb250IDw8IC9GMSA0IDAgUiA+PiA+PiAvQ29udGVudHMgNSAw"
    "IFIgPj4KZW5kb2JqCjQgMCBvYmoKPDwgL1R5cGUgL0ZvbnQgL1N1YnR5cGUgL1R5cGUxIC9CYXNl"
    "Rm9udCAvSGVsdmV0aWNhID4+CmVuZG9iago1IDAgb2JqCjw8IC9MZW5ndGggNzcgPj4Kc3RyZWFt"
    "CkJUIC9GMSAxMiBUZiA3MiA3MjAgVGQgKHpvdGVyby1jbGkgc2VsZnRlc3Q6IFBERiB0ZXh0IGV4"
    "dHJhY3Rpb24gd29ya3MpIFRqIEVUCmVuZHN0cmVhbQplbmRvYmoKeHJlZgowIDYKMDAwMDAwMDAw"
    "MCA2NTUzNSBmIAowMDAwMDAwMDA5IDAwMDAwIG4gCjAwMDAwMDAwNTggMDAwMDAgbiAKMDAwMDAw"
    "MDExNSAwMDAwMCBuIAowMDAwMDAwMjQxIDAwMDAwIG4gCjAwMDAwMDAzMTEgMDAwMDAgbiAKdHJh"
    "aWxlcgo8PCAvU2l6ZSA2IC9Sb290IDEgMCBSID4+CnN0YXJ0eHJlZgo0MzgKJSVFT0YK"
)


@dataclass
class SelfTestResult:
    name: str
    ok: bool
    detail: str


def _check_pdf_extraction() -> SelfTestResult:
    from zotero_cli.core.services.attachment_service import extract_pdf_text

    name = "PDF text extraction"
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = os.path.join(tmp_dir, "selftest.pdf")
            with open(path, "wb") as f:
                f.write(SAMPLE_PDF)
            text = extract_pdf_text(path)
    except Exception as e:
        return SelfTestResult(name, False, f"{type(e).__name__}: {e}")
    if SAMPLE_PDF_TEXT not in text:
        return SelfTestResult(name, False, f"unexpected output: {text[:80]!r}")
    return SelfTestResult(name, True, "sample PDF converted")


def _check_sqlite() -> SelfTestResult:
    name = "SQLite (offline mode)"
    try:
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute("SELECT 1").fetchone()
        finally:
            conn.close()
    except Exception as e:
        return SelfTestResult(name, False, f"{type(e).__name__}: {e}")
    return SelfTestResult(name, True, f"SQLite {sqlite3.sqlite_version}")


def run_selftest() -> List[SelfTestResult]:
    return [_check_pdf_extraction(), _check_sqlite()]
