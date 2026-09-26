"""
Pinned Hugging Face model revisions for the optional `rag` features
(GHSA-wv6f-cg7x-pg85).

Models used to be downloaded and loaded at `revision="main"`, a branch the
model's owner (or anyone who takes over the account) can move, and always
with `trust_remote_code=True`, so a changed repository could run Python on
the user's machine. Now:

- the models `rag model set` offers are pinned to a commit, for download and
  load alike;
- repository code never runs unless the user opts in with
  `trust_remote_code = true` in config.toml. The two menu models that need it
  (Jina v3, gte-Qwen2) say so; Jina's code also comes from a second
  repository, which pinning Jina's own revision doesn't cover.

Any other model named in config.toml loads at `main` with a warning.
"""

import logging
from dataclasses import dataclass
from typing import Dict, Optional

from zotero_cli.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PinnedModel:
    repo_id: str
    revision: str
    needs_remote_code: bool = False


# Revisions current on 2026-09-26 (Hugging Face API `sha`). Update
# deliberately: a new revision is new code and weights.
PINNED_MODELS: Dict[str, PinnedModel] = {
    m.repo_id: m
    for m in (
        PinnedModel("BAAI/bge-m3", "5617a9f61b028005a4858fdac845db406aefb181"),
        PinnedModel(
            "jinaai/jina-embeddings-v3",
            "ab036b023d30b4d1138c4c3bfa9f0c445ab455d6",
            needs_remote_code=True,
        ),
        PinnedModel(
            "Alibaba-NLP/gte-Qwen2-7B-instruct",
            "a8d08b36ada9cacfe34c4d6f80957772a025daf2",
            needs_remote_code=True,
        ),
        PinnedModel("Qwen/Qwen2.5-1.5B-Instruct", "989aa7980e4cf806f80c7fef2b1adb7bc71aa306"),
        PinnedModel("meta-llama/Llama-3.2-3B-Instruct", "0cb88a4f764b7a12671c53f0838cd831a0843b95"),
        PinnedModel(
            "sentence-transformers/all-MiniLM-L6-v2", "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
        ),
    )
}

# Short names sentence-transformers expands itself.
ALIASES = {"all-MiniLM-L6-v2": "sentence-transformers/all-MiniLM-L6-v2"}


@dataclass(frozen=True)
class ModelLoad:
    repo_id: str
    revision: str
    trust_remote_code: bool


def pinned(model_name: str) -> Optional[PinnedModel]:
    return PINNED_MODELS.get(ALIASES.get(model_name, model_name))


def resolve_model(model_name: str, trust_remote_code: bool = False) -> ModelLoad:
    """How to download/load `model_name`. Raises ConfigurationError for a
    pinned model that needs repository code the user hasn't allowed."""
    known = pinned(model_name)
    if known is None:
        logger.warning(
            "Model %s is not pinned by zotero-cli; loading its current 'main' revision.",
            model_name,
        )
        return ModelLoad(model_name, "main", trust_remote_code)
    if known.needs_remote_code and not trust_remote_code:
        raise ConfigurationError(
            f"{known.repo_id} runs Python code from its Hugging Face repository. "
            "Set trust_remote_code = true in the [zotero] section of config.toml (or ZOTERO_TRUST_REMOTE_CODE=1) to allow it, or choose a model "
            "that doesn't need it (e.g. BAAI/bge-m3)."
        )
    return ModelLoad(known.repo_id, known.revision, known.needs_remote_code)
