from typing import TYPE_CHECKING, Optional

from zotero_cli.core.config import ZoteroConfig
from zotero_cli.infra.arxiv_lib import ArxivLibGateway
from zotero_cli.infra.bdtd_api import BDTDAPIClient
from zotero_cli.infra.bibtex_lib import BibtexLibGateway
from zotero_cli.infra.canonical_csv_lib import CanonicalCsvLibGateway
from zotero_cli.infra.crossref_api import CrossRefAPIClient
from zotero_cli.infra.dblp_api import DBLPAPIClient
from zotero_cli.infra.eric_api import ERICAPIClient
from zotero_cli.infra.hal_api import HALAPIClient
from zotero_cli.infra.ieee_csv_lib import IeeeCsvLibGateway
from zotero_cli.infra.inspire_hep_api import InspireHEPAPIClient
from zotero_cli.infra.openalex_api import OpenAlexAPIClient
from zotero_cli.infra.pubmed_api import PubMedAPIClient
from zotero_cli.infra.ris_lib import RisLibGateway
from zotero_cli.infra.semantic_scholar_api import SemanticScholarAPIClient
from zotero_cli.infra.springer_csv_lib import SpringerCsvLibGateway
from zotero_cli.infra.unpaywall_api import UnpaywallAPIClient
from zotero_cli.infra.zbmath_api import ZBMathAPIClient

if TYPE_CHECKING:
    from zotero_cli.core.services.metadata_aggregator import MetadataAggregatorService


class MetadataClientFactory:
    """
    Constructs external bibliographic-metadata API clients (Semantic Scholar,
    CrossRef, Unpaywall, OpenAlex, PubMed, zbMATH, ERIC, HAL, INSPIRE-HEP,
    DBLP, BDTD) plus the file-format import/export gateways (arXiv, BibTeX,
    RIS, and the Springer/IEEE/canonical CSV variants).
    """

    @staticmethod
    def get_openalex_client(config: Optional[ZoteroConfig] = None) -> OpenAlexAPIClient:
        if not config:
            from zotero_cli.core.config import get_config

            config = get_config()
        return OpenAlexAPIClient(email=config.unpaywall_email)

    @staticmethod
    def get_pubmed_client(config: Optional[ZoteroConfig] = None) -> PubMedAPIClient:
        if not config:
            from zotero_cli.core.config import get_config

            config = get_config()
        return PubMedAPIClient(api_key=config.ncbi_api_key)

    @staticmethod
    def get_zbmath_client() -> ZBMathAPIClient:
        return ZBMathAPIClient()

    @staticmethod
    def get_eric_client() -> ERICAPIClient:
        return ERICAPIClient()

    @staticmethod
    def get_dblp_client() -> DBLPAPIClient:
        return DBLPAPIClient()

    @staticmethod
    def get_hal_client() -> HALAPIClient:
        return HALAPIClient()

    @staticmethod
    def get_bdtd_client() -> BDTDAPIClient:
        return BDTDAPIClient()

    @staticmethod
    def get_inspire_hep_client() -> InspireHEPAPIClient:
        return InspireHEPAPIClient()

    @staticmethod
    def get_metadata_aggregator(
        config: Optional[ZoteroConfig] = None,
    ) -> "MetadataAggregatorService":
        if not config:
            from zotero_cli.core.config import get_config as main_get_config

            config = main_get_config()

        ss_client = (
            SemanticScholarAPIClient(config.semantic_scholar_api_key)
            if config.semantic_scholar_api_key
            else SemanticScholarAPIClient()
        )
        cr_client = CrossRefAPIClient()
        up_client = (
            UnpaywallAPIClient(config.unpaywall_email)
            if config.unpaywall_email
            else UnpaywallAPIClient()
        )
        oa_client = MetadataClientFactory.get_openalex_client(config)
        pm_client = MetadataClientFactory.get_pubmed_client(config)
        zm_client = MetadataClientFactory.get_zbmath_client()
        eric_client = MetadataClientFactory.get_eric_client()
        hal_client = MetadataClientFactory.get_hal_client()
        ih_client = MetadataClientFactory.get_inspire_hep_client()
        dblp_client = MetadataClientFactory.get_dblp_client()
        bdtd_client = MetadataClientFactory.get_bdtd_client()

        from zotero_cli.core.services.metadata_aggregator import MetadataAggregatorService

        aggregator = MetadataAggregatorService(
            [
                ss_client,
                cr_client,
                up_client,
                oa_client,
                pm_client,
                zm_client,
                eric_client,
                hal_client,
                ih_client,
                dblp_client,
                bdtd_client,
            ]
        )

        # Assign attributes for compatibility with PaperImporterClient
        aggregator.semantic_scholar = ss_client
        aggregator.crossref = cr_client
        aggregator.unpaywall = up_client
        aggregator.openalex = oa_client
        aggregator.pubmed = pm_client
        aggregator.zbmath = zm_client
        aggregator.eric = eric_client
        aggregator.hal = hal_client
        aggregator.inspire_hep = ih_client
        aggregator.dblp = dblp_client
        setattr(aggregator, "bdtd", bdtd_client)

        return aggregator

    @staticmethod
    def get_arxiv_gateway() -> ArxivLibGateway:
        return ArxivLibGateway()

    @staticmethod
    def get_bibtex_gateway() -> BibtexLibGateway:
        return BibtexLibGateway()

    @staticmethod
    def get_ris_gateway() -> RisLibGateway:
        return RisLibGateway()

    @staticmethod
    def get_springer_csv_gateway() -> SpringerCsvLibGateway:
        return SpringerCsvLibGateway()

    @staticmethod
    def get_ieee_csv_gateway() -> IeeeCsvLibGateway:
        return IeeeCsvLibGateway()

    @staticmethod
    def get_canonical_csv_gateway() -> CanonicalCsvLibGateway:
        return CanonicalCsvLibGateway()
