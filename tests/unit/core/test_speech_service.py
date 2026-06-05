from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest

from zotero_cli.core.interfaces import SpeechProvider
from zotero_cli.core.services.speech_service import KokoroSpeechProvider, SpeechService
from zotero_cli.core.utils.speech_filter import TextCleaningFilter


def test_kokoro_speech_provider_init():
    provider = KokoroSpeechProvider(model_path="custom_model.pth", lang_code="b", voice="custom_voice")
    assert provider.model_path == "custom_model.pth"
    assert provider.lang_code == "b"
    assert provider.voice == "custom_voice"
    assert provider._pipeline is None


@patch("sys.modules", {})
def test_kokoro_speech_provider_pipeline_import_error():
    # If kokoro package is not present/mocked out, it should raise ImportError
    provider = KokoroSpeechProvider()
    with pytest.raises(ImportError) as excinfo:
        _ = provider.pipeline
    assert "kokoro package not installed" in str(excinfo.value)


def test_kokoro_speech_provider_pipeline_success():
    mock_pipeline_class = MagicMock()
    with patch.dict("sys.modules", {"kokoro": MagicMock(KPipeline=mock_pipeline_class)}):
        provider = KokoroSpeechProvider(lang_code="a")
        pipeline = provider.pipeline
        assert pipeline is not None
        mock_pipeline_class.assert_called_once_with(lang_code="a")


def test_kokoro_speech_provider_synthesize_empty():
    mock_pipeline = MagicMock()
    # Generator returns no audio segments
    mock_pipeline.return_value = []

    provider = KokoroSpeechProvider()
    provider._pipeline = mock_pipeline  # type: ignore[assignment]

    res = provider.synthesize("Hello", Path("out.wav"))
    assert res is False


def test_kokoro_speech_provider_synthesize_success():
    mock_pipeline = MagicMock()
    # Generator returns segments
    audio_segment = np.array([0.1, 0.2], dtype=np.float32)
    mock_pipeline.return_value = [
        ("g1", "p1", audio_segment),
        ("g2", "p2", None),  # None audio should be ignored
        ("g3", "p3", audio_segment)
    ]

    provider = KokoroSpeechProvider(voice="af_heart")
    provider._pipeline = mock_pipeline  # type: ignore[assignment]

    mock_sf = MagicMock()
    with patch.dict("sys.modules", {"soundfile": mock_sf}):
        res = provider.synthesize("Hello world", Path("out.wav"))
        assert res is True

        mock_pipeline.assert_called_once_with("Hello world", voice="af_heart", speed=1, split_pattern=r"\n+")
        mock_sf.write.assert_called_once()
        args, kwargs = mock_sf.write.call_args
        assert args[0] == "out.wav"
        assert np.array_equal(args[1], np.concatenate([audio_segment, audio_segment]))
        assert args[2] == 24000



def test_speech_service_init_defaults():
    mock_provider = Mock(spec=SpeechProvider)
    service = SpeechService(provider=mock_provider)
    assert service.provider == mock_provider
    assert isinstance(service.filter, TextCleaningFilter)


def test_speech_service_init_custom_filter():
    mock_provider = Mock(spec=SpeechProvider)
    mock_filter = Mock(spec=TextCleaningFilter)
    service = SpeechService(provider=mock_provider, cleaning_filter=mock_filter)
    assert service.provider == mock_provider
    assert service.filter == mock_filter


def test_speech_service_synthesize_text_empty_after_clean():
    mock_provider = Mock(spec=SpeechProvider)
    mock_filter = Mock(spec=TextCleaningFilter)
    mock_filter.clean.return_value = ""

    service = SpeechService(provider=mock_provider, cleaning_filter=mock_filter)
    res = service.synthesize_text("[1] [2]", Path("out.wav"))

    assert res is False
    mock_filter.clean.assert_called_once_with("[1] [2]")
    mock_provider.synthesize.assert_not_called()


def test_speech_service_synthesize_text_success():
    mock_provider = Mock(spec=SpeechProvider)
    mock_provider.synthesize.return_value = True

    mock_filter = Mock(spec=TextCleaningFilter)
    mock_filter.clean.return_value = "Hello"

    service = SpeechService(provider=mock_provider, cleaning_filter=mock_filter)
    res = service.synthesize_text("Hello [1]", Path("out.wav"))

    assert res is True
    mock_filter.clean.assert_called_once_with("Hello [1]")
    mock_provider.synthesize.assert_called_once_with("Hello", Path("out.wav"))


def test_text_cleaning_filter():
    filt = TextCleaningFilter()
    assert filt.clean("") == ""
    assert filt.clean(None) == ""

    # Test LaTeX block removal
    assert filt.clean("$$block math$$ inline $math$ text") == "inline text"

    # Test LaTeX command removal
    assert filt.clean("This is a \\section{Introduction} and \\textbf{bold} text.") == "This is a and text."

    # Test citation removal
    assert filt.clean("According to [1], we found [1, 2] and [1-3] to be true.") == "According to , we found and to be true."

    # Test author-year citation removal
    assert filt.clean("Some claim (Smith, 2020) and others (Smith et al., 2020) say otherwise.") == "Some claim and others say otherwise."

    # Test URL removal
    assert filt.clean("Check https://google.com or http://foo.bar/baz for info.") == "Check or for info."

    # Test whitespace compression
    assert filt.clean("   Leading,    multiple spaces, and trailing    ") == "Leading, multiple spaces, and trailing"

