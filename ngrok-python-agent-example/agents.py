"""
LLM Agent Abstractions
Provides a clean interface for different LLM providers
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
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


class AgentBase(ABC):
    """Base class for all LLM agents"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    @abstractmethod
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
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name/identifier of this agent"""
        pass

    def get_config(self, key: str, default: Any = None) -> Any:
        """Helper to get configuration values"""
        return self.config.get(key, default)


class EchoAgent(AgentBase):
    """Simple echo agent that repeats messages back"""

    def chat(
        self,
        message: str,
        history: Optional[List[Message]] = None
    ) -> AgentResponse:
        """Echo the message back to the user"""
        response_content = f"Echo: {message}"

        return AgentResponse(
            content=response_content,
            metadata={
                "provider": "echo",
                "mode": "fallback"
            }
        )

    @property
    def name(self) -> str:
        return "echo"


class OpenAIAgent(AgentBase):
    """OpenAI-powered agent using the Chat Completions API"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)

        # Try importing OpenAI
        try:
            import openai
            self.openai = openai
        except ImportError:
            raise ImportError(
                "OpenAI package not installed. Install with: uv add openai"
            )

        # Set up API key
        self.api_key = self.get_config("api_key") or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not provided. Set OPENAI_API_KEY environment variable."
            )

        self.openai.api_key = self.api_key

        # Configuration
        self.model = self.get_config("model", "gpt-3.5-turbo")
        self.max_tokens = self.get_config("max_tokens", 500)
        self.temperature = self.get_config("temperature", 0.7)

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
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )

            assistant_message = response.choices[0].message.content

            return AgentResponse(
                content=assistant_message,
                metadata={
                    "provider": "openai",
                    "model": self.model,
                    "tokens_used": response.usage.total_tokens,
                    "finish_reason": response.choices[0].finish_reason
                }
            )

        except Exception as e:
            raise RuntimeError(f"OpenAI API error: {str(e)}")

    @property
    def name(self) -> str:
        return f"openai-{self.model}"


class AnthropicAgent(AgentBase):
    """Anthropic Claude-powered agent (example implementation)"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)

        # Try importing Anthropic
        try:
            import anthropic
            self.anthropic = anthropic
        except ImportError:
            raise ImportError(
                "Anthropic package not installed. Install with: uv add anthropic"
            )

        # Set up API key
        self.api_key = self.get_config("api_key") or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key not provided. Set ANTHROPIC_API_KEY environment variable."
            )

        self.client = self.anthropic.Anthropic(api_key=self.api_key)

        # Configuration
        self.model = self.get_config("model", "claude-3-5-sonnet-20241022")
        self.max_tokens = self.get_config("max_tokens", 500)
        self.temperature = self.get_config("temperature", 0.7)

    def chat(
        self,
        message: str,
        history: Optional[List[Message]] = None
    ) -> AgentResponse:
        """Generate a response using Anthropic's API"""

        # Build messages list
        messages = []
        if history:
            messages = [msg.to_dict() for msg in history]
        messages.append({"role": "user", "content": message})

        try:
            # Call Anthropic API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=messages
            )

            assistant_message = response.content[0].text

            return AgentResponse(
                content=assistant_message,
                metadata={
                    "provider": "anthropic",
                    "model": self.model,
                    "tokens_used": response.usage.input_tokens + response.usage.output_tokens,
                    "stop_reason": response.stop_reason
                }
            )

        except Exception as e:
            raise RuntimeError(f"Anthropic API error: {str(e)}")

    @property
    def name(self) -> str:
        return f"anthropic-{self.model}"


class AgentFactory:
    """Factory for creating agent instances"""

    _registry = {
        "echo": EchoAgent,
        "openai": OpenAIAgent,
        "anthropic": AnthropicAgent,
    }

    @classmethod
    def create(
        cls,
        provider: str,
        config: Optional[Dict[str, Any]] = None
    ) -> AgentBase:
        """
        Create an agent instance

        Args:
            provider: The provider name (e.g., "openai", "anthropic", "echo")
            config: Configuration dictionary for the agent

        Returns:
            An instance of the requested agent

        Raises:
            ValueError: If provider is not supported
        """
        if provider not in cls._registry:
            available = ", ".join(cls._registry.keys())
            raise ValueError(
                f"Unknown provider '{provider}'. Available: {available}"
            )

        agent_class = cls._registry[provider]
        return agent_class(config)

    @classmethod
    def create_from_env(cls) -> AgentBase:
        """
        Create an agent based on environment variables

        Environment variables:
            AGENT_PROVIDER: Which provider to use (default: openai)
            OPENAI_API_KEY: OpenAI API key
            ANTHROPIC_API_KEY: Anthropic API key
            MODEL: Model to use
            MAX_TOKENS: Maximum tokens in response
            TEMPERATURE: Temperature for generation

        Returns:
            An agent instance, falls back to EchoAgent if API keys are missing
        """
        provider = os.getenv("AGENT_PROVIDER", "openai").lower()

        config = {
            "model": os.getenv("MODEL"),
            "max_tokens": int(os.getenv("MAX_TOKENS", "500")),
            "temperature": float(os.getenv("TEMPERATURE", "0.7")),
        }

        # Try to create the requested provider, fall back to echo if it fails
        try:
            return cls.create(provider, config)
        except (ValueError, ImportError) as e:
            print(f"⚠️  Could not create {provider} agent: {e}")
            print(f"⚠️  Falling back to echo agent")
            return cls.create("echo")

    @classmethod
    def register(cls, name: str, agent_class: type):
        """Register a custom agent class"""
        cls._registry[name] = agent_class
