$version: "2.0"

namespace com.zoterocli.rag

/// Formal Contract for RAG Ingestion v1.0
/// Presided by Hamilton (Sovereign Architect)
service RAGIngestService {
    version: "1.0",
    operations: [IngestItems]
}

/// Operation to ingest pre-selected items into the vector store.
/// Follows the Predicate-Driven Selection Strategy [SPEC-RAG-001].
operation IngestItems {
    input: IngestItemsInput,
    output: IngestStats
}

structure IngestItemsInput {
    /// List of pre-filtered Zotero item keys to ingest.
    @required
    itemKeys: ItemKeyList,
    
    /// Whether to prune the vector store before ingestion.
    prune: Boolean = false,
    
    /// Optional minimum QA score threshold [SPEC-RAG-002].
    minQaScore: Float
}

structure IngestStats {
    @required
    processed: Integer,
    @required
    skippedNoText: Integer,
    @required
    skippedLowQa: Integer
}

list ItemKeyList {
    member: String
}
