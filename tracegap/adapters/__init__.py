"""Adapter registry. Each factory imports its framework lazily."""


def _langgraph():
    from .langgraph_cb import LangGraphCallbacks

    return LangGraphCallbacks()


def _openai_agents():
    from .openai_agents_tracing import OpenAIAgentsTracing

    return OpenAIAgentsTracing()


def _pai_history():
    from .pydantic_ai_adapters import PydanticAIHistory

    return PydanticAIHistory()


def _pai_otel():
    from .pydantic_ai_adapters import PydanticAIOtel

    return PydanticAIOtel()


def _ag_messages():
    from .autogen_adapters import AutoGenMessages

    return AutoGenMessages()


def _ag_otel():
    from .autogen_adapters import AutoGenOtel

    return AutoGenOtel()


def _lazy(module: str, cls: str):
    def factory():
        import importlib

        return getattr(importlib.import_module(f"{__name__}.{module}"), cls)()

    return factory


ADAPTERS = {
    "autogen/messages": _ag_messages,
    "autogen/otel": _ag_otel,
    "langgraph/callbacks": _langgraph,
    "openai-agents/tracing": _openai_agents,
    "pydantic-ai/history": _pai_history,
    "pydantic-ai/otel": _pai_otel,
    "smolagents/memory": _lazy("smolagents_adapters", "SmolagentsMemory"),
    "smolagents/openinference": _lazy("smolagents_adapters", "SmolagentsOpenInference"),
    "llamaindex/events": _lazy("llamaindex_adapters", "LlamaIndexEvents"),
    "llamaindex/openinference": _lazy("llamaindex_adapters", "LlamaIndexOpenInference"),
    "semantic-kernel/filters": _lazy("semantic_kernel_adapters", "SemanticKernelFilters"),
    "semantic-kernel/otel": _lazy("semantic_kernel_adapters", "SemanticKernelOtel"),
    "google-adk/events": _lazy("adk_adapters", "ADKEvents"),
    "google-adk/otel": _lazy("adk_adapters", "ADKOtel"),
    "crewai/events": _lazy("crewai_adapters", "CrewAIEvents"),
}
