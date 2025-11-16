"""Tests for the agent abstraction layer"""

import pytest
from agents import Message, AgentResponse, EchoAgent, create_agent, create_agent_from_env


class TestMessage:
    """Test Message class"""

    def test_message_creation(self):
        """Test creating a message"""
        msg = Message("user", "Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_message_to_dict(self):
        """Test converting message to dict"""
        msg = Message("assistant", "Hi there")
        result = msg.to_dict()
        assert result == {"role": "assistant", "content": "Hi there"}

    def test_message_from_dict(self):
        """Test creating message from dict"""
        data = {"role": "user", "content": "Test"}
        msg = Message.from_dict(data)
        assert msg.role == "user"
        assert msg.content == "Test"

    def test_message_invalid_role_type(self):
        """Test that Message raises TypeError for non-string role"""
        with pytest.raises(TypeError, match="role must be a string"):
            Message(None, "content")  # type: ignore[arg-type]

    def test_message_invalid_content_type(self):
        """Test that Message raises TypeError for non-string content"""
        with pytest.raises(TypeError, match="content must be a string"):
            Message("user", None)  # type: ignore[arg-type]

    def test_message_empty_strings(self):
        """Test that Message accepts empty strings"""
        msg = Message("", "")
        assert msg.role == ""
        assert msg.content == ""


class TestAgentResponse:
    """Test AgentResponse class"""

    def test_response_creation(self):
        """Test creating a response with metadata"""
        response = AgentResponse("Test response", {"model": "echo"})
        assert response.content == "Test response"
        assert response.metadata["model"] == "echo"

    def test_response_creation_no_metadata(self):
        """Test creating a response without metadata"""
        response = AgentResponse("Test")
        assert response.content == "Test"
        assert response.metadata == {}

    def test_response_to_dict(self):
        """Test converting response to dict"""
        response = AgentResponse("Test", {"model": "echo"})
        result = response.to_dict()
        assert result["content"] == "Test"
        assert result["metadata"]["model"] == "echo"

    def test_response_invalid_content_type(self):
        """Test that AgentResponse raises TypeError for non-string content"""
        with pytest.raises(TypeError, match="content must be a string"):
            AgentResponse(None)  # type: ignore[arg-type]

    def test_response_empty_content(self):
        """Test that AgentResponse accepts empty string content"""
        response = AgentResponse("")
        assert response.content == ""
        assert response.metadata == {}


class TestEchoAgent:
    """Test EchoAgent class"""

    def test_agent_chat_no_history(self):
        """Test agent echoes message without history"""
        agent = EchoAgent()
        response = agent.chat("Hello")

        assert isinstance(response, AgentResponse)
        assert response.content == "Echo: Hello"
        assert response.metadata["message_count"] == 0
        assert response.metadata["echo_length"] == 5

    def test_agent_chat_with_history(self):
        """Test agent echoes message with history"""
        agent = EchoAgent()
        history = [
            Message("user", "First message"),
            Message("assistant", "Echo: First message"),
            Message("user", "Second message"),
            Message("assistant", "Echo: Second message"),
        ]

        response = agent.chat("Third message", history=history)

        assert response.content == "Echo: Third message"
        assert response.metadata["message_count"] == 4
        assert response.metadata["echo_length"] == 13

    def test_agent_name(self):
        """Test agent name property"""
        agent = EchoAgent()
        assert agent.name == "echo-agent"

    def test_agent_empty_message(self):
        """Test agent handles empty message"""
        agent = EchoAgent()
        response = agent.chat("")

        assert response.content == "Echo: "
        assert response.metadata["echo_length"] == 0


class TestFactoryFunctions:
    """Test factory functions"""

    def test_create_agent(self):
        """Test create_agent factory"""
        agent = create_agent()
        assert isinstance(agent, EchoAgent)
        assert agent.name == "echo-agent"

    def test_create_agent_with_config(self):
        """Test create_agent factory with config (ignored)"""
        config = {"some": "config"}
        agent = create_agent(config)
        assert isinstance(agent, EchoAgent)

    def test_create_agent_from_env(self):
        """Test create_agent_from_env factory"""
        agent = create_agent_from_env()
        assert isinstance(agent, EchoAgent)
        assert agent.name == "echo-agent"
