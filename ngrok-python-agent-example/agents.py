"""
Agent Abstractions
Provides a clean interface for conversational agents
"""

from typing import Protocol, Optional, Any


class Message:
    """Represents a single message in a conversation"""

    def __init__(self, role: str, content: str):
        if not isinstance(role, str):
            raise TypeError(f"role must be a string, got {type(role).__name__}")
        if not isinstance(content, str):
            raise TypeError(f"content must be a string, got {type(content).__name__}")
        self.role = role
        self.content = content

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "Message":
        return cls(role=data["role"], content=data["content"])


class AgentResponse:
    """Standard response format from an agent"""

    def __init__(self, content: str, metadata: Optional[dict[str, Any]] = None):
        if not isinstance(content, str):
            raise TypeError(f"content must be a string, got {type(content).__name__}")
        self.content = content
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        return {"content": self.content, "metadata": self.metadata}


class Agent(Protocol):
    """
    Protocol defining the agent interface

    Any class implementing this protocol must provide:
    - chat(message, history) -> AgentResponse
    - name property
    """

    @property
    def name(self) -> str:
        """Return the name/identifier of this agent"""
        ...

    def chat(self, message: str, history: Optional[list[Message]] = None) -> AgentResponse:
        """
        Process a chat message and return a response

        Args:
            message: The user's message
            history: Previous conversation history

        Returns:
            AgentResponse with the agent's reply and metadata
        """
        ...


class EchoAgent:
    """Simple echo agent that repeats the user's message"""

    def chat(self, message: str, history: Optional[list[Message]] = None) -> AgentResponse:
        """Echo the user's message back with conversation context"""
        message_count = len(history) if history else 0

        return AgentResponse(
            content=f"Echo: {message}",
            metadata={
                "message_count": message_count,
                "echo_length": len(message),
            },
        )

    @property
    def name(self) -> str:
        return "echo-agent"


def create_agent(config: Optional[dict[str, Any]] = None) -> Agent:
    """
    Create an agent instance

    Args:
        config: Configuration dictionary for the agent (unused for echo agent)

    Returns:
        An EchoAgent instance
    """
    return EchoAgent()


def create_agent_from_env() -> Agent:
    """
    Create an agent from environment variables

    Returns:
        An EchoAgent instance
    """
    return EchoAgent()
