"""Tests for the agent abstraction layer"""

import sys
import pytest
from unittest.mock import Mock, patch, MagicMock
from agents import Message, AgentResponse, create_agent, create_agent_from_env

# Mock the openai module before importing LLMAgent
mock_openai = MagicMock()
sys.modules["openai"] = mock_openai

from agents import LLMAgent  # noqa: E402


class TestMessage:
    """Test Message class"""

    def test_message_creation(self):
        msg = Message("user", "Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_message_to_dict(self):
        msg = Message("assistant", "Hi there")
        assert msg.to_dict() == {"role": "assistant", "content": "Hi there"}

    def test_message_from_dict(self):
        data = {"role": "user", "content": "Test"}
        msg = Message.from_dict(data)
        assert msg.role == "user"
        assert msg.content == "Test"


class TestAgentResponse:
    """Test AgentResponse class"""

    def test_response_creation(self):
        response = AgentResponse("Hello", {"tokens": 10})
        assert response.content == "Hello"
        assert response.metadata == {"tokens": 10}

    def test_response_creation_no_metadata(self):
        response = AgentResponse("Hello")
        assert response.content == "Hello"
        assert response.metadata == {}

    def test_response_to_dict(self):
        response = AgentResponse("Test", {"model": "gpt-4o"})
        result = response.to_dict()
        assert result["content"] == "Test"
        assert result["metadata"]["model"] == "gpt-4o"


class TestLLMAgent:
    """Test LLMAgent class"""

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_agent_initialization(self):
        """Test agent initializes correctly"""
        mock_openai.OpenAI.reset_mock()
        agent = LLMAgent()
        assert agent.model == "gpt-4o"
        mock_openai.OpenAI.assert_called_once_with(api_key="test-key")

    def test_agent_initialization_with_config(self):
        """Test agent initializes with custom config"""
        mock_openai.OpenAI.reset_mock()
        config = {"api_key": "custom-key", "model": "gpt-4-turbo"}
        agent = LLMAgent(config)
        assert agent.model == "gpt-4-turbo"
        mock_openai.OpenAI.assert_called_once_with(api_key="custom-key")

    @patch.dict("os.environ", {}, clear=True)
    def test_agent_initialization_missing_api_key(self):
        """Test agent raises error when API key is missing"""
        with pytest.raises(ValueError, match="OpenAI API key not provided"):
            LLMAgent()

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "MODEL": "gpt-4"})
    def test_agent_uses_env_model(self):
        """Test agent uses model from environment"""
        mock_openai.OpenAI.reset_mock()
        agent = LLMAgent()
        assert agent.model == "gpt-4"

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_agent_chat(self):
        """Test chat functionality"""
        # Mock OpenAI response
        mock_openai.OpenAI.reset_mock()
        mock_client = Mock()
        mock_openai.OpenAI.return_value = mock_client
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Hello!"), finish_reason="stop")]
        mock_response.usage = Mock(total_tokens=50)
        mock_client.chat.completions.create.return_value = mock_response

        agent = LLMAgent()
        response = agent.chat("Hi there")

        assert isinstance(response, AgentResponse)
        assert response.content == "Hello!"
        assert response.metadata["tokens_used"] == 50
        assert response.metadata["model"] == "gpt-4o"
        assert response.metadata["finish_reason"] == "stop"

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_agent_chat_with_history(self):
        """Test chat with conversation history"""
        mock_openai.OpenAI.reset_mock()
        mock_client = Mock()
        mock_openai.OpenAI.return_value = mock_client
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Response"), finish_reason="stop")]
        mock_response.usage = Mock(total_tokens=30)
        mock_client.chat.completions.create.return_value = mock_response

        agent = LLMAgent()
        history = [Message("user", "Hello"), Message("assistant", "Hi")]

        agent.chat("How are you?", history=history)

        # Verify the API was called with the correct messages
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        assert len(messages) == 3
        assert messages[0] == {"role": "user", "content": "Hello"}
        assert messages[1] == {"role": "assistant", "content": "Hi"}
        assert messages[2] == {"role": "user", "content": "How are you?"}

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_agent_chat_api_error(self):
        """Test chat handles API errors correctly"""
        mock_openai.OpenAI.reset_mock()
        mock_client = Mock()
        mock_openai.OpenAI.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        agent = LLMAgent()

        with pytest.raises(RuntimeError, match="LLM API error"):
            agent.chat("Test message")

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_agent_name(self):
        """Test agent name property"""
        mock_openai.OpenAI.reset_mock()
        agent = LLMAgent()
        assert agent.name == "llm-gpt-4o"

        agent_custom = LLMAgent({"api_key": "key", "model": "gpt-4-turbo"})
        assert agent_custom.name == "llm-gpt-4-turbo"


class TestFactoryFunctions:
    """Test factory functions"""

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_create_agent(self):
        """Test create_agent factory"""
        mock_openai.OpenAI.reset_mock()
        config = {"api_key": "test-key", "model": "gpt-4"}
        agent = create_agent(config)
        assert agent.model == "gpt-4"
        assert isinstance(agent, LLMAgent)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_create_agent_from_env(self):
        """Test create_agent_from_env factory"""
        mock_openai.OpenAI.reset_mock()
        agent = create_agent_from_env()
        assert agent.model == "gpt-4o"
        assert isinstance(agent, LLMAgent)
