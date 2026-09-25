# Data Sources

zotero-cli reads from your Zotero library and, for metadata lookups, PDF discovery and citation snowballing, from the public scholarly services below. **zotero-cli is an independent project. It is not affiliated with, sponsored by or endorsed by Zotero or the Corporation for Digital Scholarship, arXiv, or any provider listed here.**

Your use of each service is subject to that provider's terms. Read them before bulk or automated use; the links below are where each provider documents its API and usage terms.

## How zotero-cli identifies itself

Every request carries an honest User-Agent: `zotero-cli/<version> (+https://github.com/fchicout/zotero-cli)`. If you set `unpaywall_email` in your config, it's added as `mailto:<your address>`, which Crossref and OpenAlex use to place requests in their "polite pool". zotero-cli never sends a browser User-Agent, and never retries a refused request under a different identity. A `403` with an API key fails with a message saying the key was rejected.

API keys you configure (Zotero, Semantic Scholar, CORE, NCBI, ...) are sent only to the provider they belong to, and are stripped when a redirect leaves that provider's origin.

## Providers

| Provider | Used for | Endpoint | Terms / API documentation |
| :--- | :--- | :--- | :--- |
| Zotero Web API | Your library (every online command) | `api.zotero.org` | <https://www.zotero.org/support/dev/web_api/v3/start> |
| Crossref | DOI metadata, references | `api.crossref.org` | <https://www.crossref.org/documentation/retrieve-metadata/rest-api/> |
| Semantic Scholar | Citations and references (snowballing), PDFs | `api.semanticscholar.org` | <https://www.semanticscholar.org/product/api/license> |
| OpenAlex | Metadata, open-access PDFs | `api.openalex.org` | <https://docs.openalex.org/> |
| Unpaywall | Open-access PDF locations | `api.unpaywall.org` | <https://unpaywall.org/products/api> |
| arXiv | Metadata, PDFs | `export.arxiv.org`, `arxiv.org` | <https://info.arxiv.org/help/api/tou.html> |
| PubMed / NCBI E-utilities | Metadata, PMID/PMC conversion | `eutils.ncbi.nlm.nih.gov`, `www.ncbi.nlm.nih.gov` | <https://www.ncbi.nlm.nih.gov/books/NBK25497/> |
| CORE | Search | `api.core.ac.uk` | <https://core.ac.uk/terms> |
| DOAJ | Search | `doaj.org/api` | <https://doaj.org/api/> |
| DBLP | Search | `dblp.org` | <https://dblp.org/faq/> |
| HAL | Search | `api.archives-ouvertes.fr` | <https://api.archives-ouvertes.fr/docs> |
| INSPIRE-HEP | Search | `inspirehep.net` | <https://inspirehep.net/help/knowledge-base/terms-of-use> |
| zbMATH Open | Search | `api.zbmath.org` | <https://zbmath.org/> |
| ERIC | Search | `api.ies.ed.gov/eric` | <https://eric.ed.gov/> |
| BDTD (IBICT) | Brazilian theses and dissertations, PDFs from university repositories | `bdtd.ibict.br` | <https://bdtd.ibict.br/> |

## Attribution

- **Semantic Scholar:** citation data used by `slr snowball` comes from the Semantic Scholar API. The Semantic Scholar API License Agreement asks that published materials using the data attribute it to Semantic Scholar. If you publish results produced with `slr snowball`, credit Semantic Scholar.
- **Other providers:** follow the attribution and licence terms in each provider's documentation above.
