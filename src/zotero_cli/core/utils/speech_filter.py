import re


class TextCleaningFilter:
    """
    Cleans text for Text-to-Speech by removing citations, LaTeX math, and URLs.
    """

    def clean(self, text: str) -> str:
        if not text:
            return ""

        # Remove LaTeX blocks: $...$ or $$...$$
        text = re.sub(r"\$\$.*?\$\$", "", text, flags=re.DOTALL)
        text = re.sub(r"\$.*?\$", "", text)

        # Remove common LaTeX commands: \section{}, \textbf{}, etc.
        text = re.sub(r"\\\w+\{.*?\}", "", text)

        # Remove citations like [1], [1, 2], [1-3]
        text = re.sub(r"\[\d+([\s,.-]+\d+)*\]", "", text)

        # Remove author-year citations like (Smith, 2020) or (Smith et al., 2020)
        # Simplified: (Name, Year)
        text = re.sub(r"\([A-Z][a-z]+(\s+et\s+al\.)?,\s+\d{4}\)", "", text)

        # Remove URLs
        text = re.sub(r"https?://\S+", "", text)

        # Clean up whitespace
        text = re.sub(r"\s+", " ", text).strip()

        return text
