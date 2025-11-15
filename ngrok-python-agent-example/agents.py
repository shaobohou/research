"""
LLM Agent Abstractions
Provides a clean interface for LLM-powered agents
"""

from typing import List, Dict, Optional, Any, Protocol
import os


class Message:
    """Represents a single message in a conversation"""

    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content

    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "Message":
        return cls(role=data["role"], content=data["content"])


class AgentResponse:
    """Standard response format from an agent"""

    def __init__(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.content = content
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "metadata": self.metadata
        }


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

    def chat(
        self,
        message: str,
        history: Optional[List[Message]] = None
    ) -> AgentResponse:
        """
        Process a chat message and return a response

        Args:
            message: The user's message
            history: Previous conversation history

        Returns:
            AgentResponse with the agent's reply and metadata
        """
        ...


class LLMAgent:
    """LLM-powered agent using OpenAI's Chat Completions API"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

        # Try importing OpenAI
        try:
            import openai
            self.openai = openai
        except ImportError:
            raise ImportError(
                "OpenAI package not installed. Install with: uv sync"
            )

        # Set up API key (from config or environment)
        self.api_key = self._get_config("api_key") or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not provided. Set OPENAI_API_KEY environment variable."
            )

        self.openai.api_key = self.api_key

        # Model configuration (prioritize: config dict > environment > default)
        self.model = (
            self._get_config("model")
            or os.getenv("MODEL")
            or "gpt-4o"
        )

    def _get_config(self, key: str, default: Any = None) -> Any:
        """Helper to get configuration values"""
        return self.config.get(key, default)

    def chat(
        self,
        message: str,
        history: Optional[List[Message]] = None
    ) -> AgentResponse:
        """Generate a response using OpenAI's API"""

        # Build messages list
        messages = []
        if history:
            messages = [msg.to_dict() for msg in history]
        messages.append({"role": "user", "content": message})

        try:
            # Call OpenAI API
            response = self.openai.ChatCompletion.create(
                model=self.model,
                messages=messages
            )

            assistant_message = response.choices[0].message.content

            return AgentResponse(
                content=assistant_message,
                metadata={
                    "model": self.model,
                    "tokens_used": response.usage.total_tokens,
                    "finish_reason": response.choices[0].finish_reason
                }
            )

        except Exception as e:
            raise RuntimeError(f"LLM API error: {str(e)}")

    @property
    def name(self) -> str:
        return f"llm-{self.model}"


def create_agent(config: Optional[Dict[str, Any]] = None) -> Agent:
    """
    Create an LLM agent instance

    Args:
        config: Configuration dictionary for the agent
                Can include: api_key, model

    Returns:
        An LLMAgent instance

    Raises:
        ValueError: If API key is not provided
        ImportError: If OpenAI package is not installed
    """
    return LLMAgent(config)


def create_agent_from_env() -> Agent:
    """
    Create an LLM agent from environment variables

    Environment variables:
        OPENAI_API_KEY: OpenAI API key (required)
        MODEL: Model to use (optional, default: gpt-4o)

    Returns:
        An LLMAgent instance
    """
    return LLMAgent()
