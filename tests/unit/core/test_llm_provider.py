from unittest.mock import MagicMock, patch

import pytest

from zotero_cli.core.services.llm_provider import (
    GeminiLLMProvider,
    LocalTransformersLLMProvider,
    MockLLMProvider,
    OpenAILLMProvider,
)


def test_mock_llm_provider():
    provider = MockLLMProvider()
    res = provider.generate("Summarize this paper", "You are an AI assistant")
    assert "[MOCK SUMMARY]" in res
    assert "Summarize this paper" in res


def test_openai_llm_provider_import_error():
    with patch.dict("sys.modules", {"openai": None}):
        provider = OpenAILLMProvider(api_key="fake_key")
        # Since client is None when package is not importable
        with pytest.raises(ImportError) as excinfo:
            provider.generate("hello")
        assert "openai package not installed" in str(excinfo.value)


def test_openai_llm_provider_generate():
    mock_openai = MagicMock()
    mock_client = MagicMock()
    mock_openai.OpenAI.return_value = mock_client

    # Mock return value structure: client.chat.completions.create().choices[0].message.content
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "openai generated response"
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    with patch.dict("sys.modules", {"openai": mock_openai}):
        provider = OpenAILLMProvider(api_key="fake_key")
        res = provider.generate("hello prompt", system_instruction="system rule")
        assert res == "openai generated response"
        mock_openai.OpenAI.assert_called_once_with(api_key="fake_key")
        mock_client.chat.completions.create.assert_called_once()
        args, kwargs = mock_client.chat.completions.create.call_args
        assert kwargs["model"] == "gpt-4o"
        assert kwargs["messages"] == [
            {"role": "system", "content": "system rule"},
            {"role": "user", "content": "hello prompt"},
        ]


def test_gemini_llm_provider_import_error():
    with patch.dict("sys.modules", {"google.generativeai": None}):
        provider = GeminiLLMProvider(api_key="fake_key")
        with pytest.raises(ImportError) as excinfo:
            provider.generate("hello")
        assert "google-generativeai package not installed" in str(excinfo.value)


@patch("google.generativeai.GenerativeModel")
@patch("google.generativeai.configure")
def test_gemini_llm_provider_generate(mock_configure, mock_generative_model):
    mock_model = MagicMock()
    mock_generative_model.return_value = mock_model

    mock_response = MagicMock()
    mock_response.text = "gemini generated response"
    mock_model.generate_content.return_value = mock_response

    provider = GeminiLLMProvider(api_key="fake_key")
    res = provider.generate("hello prompt", system_instruction="system rule")
    assert res == "gemini generated response"
    mock_configure.assert_called_once_with(api_key="fake_key")
    mock_generative_model.assert_called_once_with(model_name="gemini-2.0-flash-exp")
    mock_model.generate_content.assert_called_once_with("system rule\n\nUser Request: hello prompt")


def test_local_transformers_llm_provider():
    mock_transformers = MagicMock()
    mock_model_obj = MagicMock()
    mock_tokenizer_obj = MagicMock()

    mock_transformers.AutoModelForCausalLM.from_pretrained.return_value = mock_model_obj
    mock_transformers.AutoTokenizer.from_pretrained.return_value = mock_tokenizer_obj

    mock_tokenizer_obj.apply_chat_template.return_value = "formatted template"
    mock_inputs = MagicMock()
    mock_inputs.to.return_value = mock_inputs
    mock_inputs.input_ids = [[1, 2, 3]]
    mock_tokenizer_obj.return_value = mock_inputs

    mock_model_obj.device = "cpu"
    mock_model_obj.generate.return_value = [[1, 2, 3, 4, 5]] # output_ids length > input_ids length

    mock_tokenizer_obj.batch_decode.return_value = ["local transformers response"]

    with patch.dict("sys.modules", {"transformers": mock_transformers}):
        provider = LocalTransformersLLMProvider()
        res = provider.generate("hello prompt", system_instruction="system rule")
        assert res == "local transformers response"

        mock_transformers.AutoTokenizer.from_pretrained.assert_called_once_with(
            "Qwen/Qwen2.5-1.5B-Instruct", revision="main"
        )
        mock_transformers.AutoModelForCausalLM.from_pretrained.assert_called_once()
        mock_tokenizer_obj.apply_chat_template.assert_called_once_with(
            [
                {"role": "system", "content": "system rule"},
                {"role": "user", "content": "hello prompt"},
            ],
            tokenize=False,
            add_generation_prompt=True,
        )
        mock_model_obj.generate.assert_called_once()
        mock_tokenizer_obj.batch_decode.assert_called_once_with([[4, 5]], skip_special_tokens=True)
