from pathlib import Path
from typing import Optional

from zotero_cli.core.interfaces import SpeechProvider
from zotero_cli.core.utils.speech_filter import TextCleaningFilter


class KokoroSpeechProvider(SpeechProvider):
    """
    Speech provider using Kokoro TTS.
    """

    def __init__(
        self, model_path: Optional[str] = None, lang_code: str = "a", voice: str = "af_heart"
    ):
        self.model_path = model_path
        self.lang_code = lang_code
        self.voice = voice
        self._pipeline = None

    @property
    def pipeline(self):
        if self._pipeline is None:
            try:
                from kokoro import KPipeline

                # Initialize pipeline for English (or configurable)
                self._pipeline = KPipeline(lang_code=self.lang_code)
            except ImportError:
                raise ImportError("kokoro package not installed. Run 'pip install kokoro'")
        return self._pipeline

    def synthesize(self, text: str, output_path: Path) -> bool:
        import numpy as np
        import soundfile as sf

        generator = self.pipeline(
            text,
            voice=self.voice,
            speed=1,
            split_pattern=r"\n+",
        )

        all_audio = []
        for gs, ps, audio in generator:
            if audio is not None:
                all_audio.append(audio)

        if not all_audio:
            return False

        full_audio = np.concatenate(all_audio)
        sf.write(str(output_path), full_audio, 24000)
        return True


class SpeechService:
    """
    Orchestrates text-to-speech with cleaning.
    """

    def __init__(
        self, provider: SpeechProvider, cleaning_filter: Optional[TextCleaningFilter] = None
    ):
        self.provider = provider
        self.filter = cleaning_filter or TextCleaningFilter()

    def synthesize_text(self, text: str, output_path: Path) -> bool:
        clean_text = self.filter.clean(text)
        if not clean_text:
            return False
        return self.provider.synthesize(clean_text, output_path)
