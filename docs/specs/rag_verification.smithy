$version: "2.0"

namespace com.zoterocli.rag

/// Formal Contract for RAG Verification v1.1
/// Presided by Hamilton (Sovereign Architect)
service RAGService {
    version: "1.1",
    operations: [VerifyResults]
}

@readonly
operation VerifyResults {
    input: SearchResultsInput,
    output: VerifiedResultsOutput
}

structure SearchResultsInput {
    @required
    results: SearchResults
}

structure VerifiedResultsOutput {
    @required
    verifiedResults: VerifiedSearchResults
}

list SearchResults {
    member: SearchResult
}

list VerifiedSearchResults {
    member: VerifiedSearchResult
}

structure SearchResult {
    @required
    itemKey: String,
    @required
    text: String,
    @required
    score: Float,
    metadata: MetadataMap
}

structure VerifiedSearchResult {
    @required
    itemKey: String,
    @required
    text: String,
    @required
    score: Float,
    metadata: MetadataMap,
    
    @required
    isVerified: Boolean,
    
    @required
    verificationErrors: ErrorList,
    
    @required
    screeningStatus: ScreeningStatus,
    
    citationKey: String
}

map MetadataMap {
    key: String,
    value: String
}

list ErrorList {
    member: String
}

enum ScreeningStatus {
    ACCEPTED = "accepted",
    REJECTED = "rejected",
    PENDING = "pending",
    UNKNOWN = "unknown"
}
