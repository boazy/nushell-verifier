import pytest
from unittest.mock import patch, MagicMock
from nushell_verifier.llm_client import LLMClient
from nushell_verifier.models import Config


def test_safe_params_gpt4():
    """Test safe parameters for GPT-4 (supports temperature)."""
    config = Config(llm_provider="openai", llm_model="gpt-4")
    client = LLMClient(config)

    params = client._get_safe_params()

    assert "temperature" in params
    assert params["temperature"] == 0.1
    assert "max_tokens" in params
    assert params["max_tokens"] == 4000


def test_safe_params_gpt5():
    """Test safe parameters for GPT-5 (no temperature support)."""
    config = Config(llm_provider="openai", llm_model="gpt-5")
    client = LLMClient(config)

    params = client._get_safe_params()

    assert "temperature" not in params
    assert "max_tokens" in params
    assert params["max_tokens"] == 4000


def test_safe_params_with_custom_temperature():
    """Test safe parameters with custom temperature from config."""
    config = Config(llm_provider="openai", llm_model="gpt-4", temperature=0.5)
    client = LLMClient(config)

    params = client._get_safe_params()

    assert params["temperature"] == 0.5


def test_safe_params_with_llm_params():
    """Test safe parameters with custom llm_params from config."""
    config = Config(
        llm_provider="openai",
        llm_model="gpt-4",
        llm_params={"top_p": 0.9, "max_tokens": 2000}
    )
    client = LLMClient(config)

    params = client._get_safe_params()

    assert params["top_p"] == 0.9
    assert params["max_tokens"] == 2000  # Should override default


def test_safe_params_unsupported_model():
    """Test safe parameters for unknown model (uses default)."""
    config = Config(llm_provider="unknown", llm_model="unknown-model")
    client = LLMClient(config)

    params = client._get_safe_params()

    assert "temperature" not in params  # Default doesn't support temperature
    assert "max_tokens" in params
    assert "top_p" not in params  # Default doesn't support top_p


def test_safe_params_anthropic():
    """Test safe parameters for Anthropic models."""
    config = Config(llm_provider="anthropic", llm_model="claude-3-sonnet")
    client = LLMClient(config)

    params = client._get_safe_params()

    assert "temperature" in params
    assert params["temperature"] == 0.1
    assert "max_tokens" in params


def test_safe_params_custom_params_override():
    """Test that custom_params parameter works correctly."""
    config = Config(llm_provider="openai", llm_model="gpt-4")
    client = LLMClient(config)

    params = client._get_safe_params(custom_params={"temperature": 0.8})

    assert params["temperature"] == 0.8


def test_safe_params_filters_unsupported():
    """Test that unsupported parameters are filtered out."""
    config = Config(
        llm_provider="openai",
        llm_model="gpt-5",  # Doesn't support temperature
        llm_params={"temperature": 0.5, "max_tokens": 2000}
    )
    client = LLMClient(config)

    params = client._get_safe_params()

    assert "temperature" not in params  # Should be filtered out
    assert params["max_tokens"] == 2000  # Should be included


@patch('litellm.completion')
def test_convert_blog_to_instructions_uses_safe_params(mock_completion):
    """Test that convert_blog_to_instructions uses safe parameters."""
    from nushell_verifier.models import ReleaseInfo

    # Mock the response
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Test instructions"
    mock_completion.return_value = mock_response

    config = Config(llm_provider="openai", llm_model="gpt-5")  # No temperature support
    client = LLMClient(config)

    release = ReleaseInfo(version="0.95.0", blog_post_url="test")
    result = client.convert_blog_to_instructions(release, "test content")

    # Verify the call was made without temperature
    mock_completion.assert_called_once()
    call_args = mock_completion.call_args

    assert "temperature" not in call_args[1]
    assert "max_tokens" in call_args[1]
    assert call_args[1]["model"] == "openai/gpt-5"


@patch('litellm.completion')
@patch('builtins.open')
def test_analyze_script_compatibility_uses_safe_params(mock_open, mock_completion):
    """Test that analyze_script_compatibility uses safe parameters."""
    from nushell_verifier.models import ScriptFile, CompatibilityMethod
    from pathlib import Path

    # Mock file reading
    mock_open.return_value.__enter__.return_value.read.return_value = "echo 'test'"

    # Mock the response
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "COMPATIBLE"
    mock_completion.return_value = mock_response

    config = Config(llm_provider="openai", llm_model="gpt-4", temperature=0.2)
    client = LLMClient(config)

    script = ScriptFile(
        path=Path("test.nu"),
        compatible_version="0.90.0",
        method=CompatibilityMethod.COMMENT_HEADER
    )

    result = client.analyze_script_compatibility(script, "0.95.0", ["test instructions"])

    # Verify the call was made with correct temperature
    mock_completion.assert_called_once()
    call_args = mock_completion.call_args

    assert call_args[1]["temperature"] == 0.2
    assert "max_tokens" in call_args[1]
    assert result == []  # COMPATIBLE response should return empty list