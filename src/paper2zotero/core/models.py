from dataclasses import dataclass

@dataclass
class ArxivPaper:
    arxiv_id: str
    title: str
    abstract: str
