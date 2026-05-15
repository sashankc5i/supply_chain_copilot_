"""Compatibility shim for the @tool decorator.

When langchain_core is installed, `@tool` wraps the function as a
StructuredTool (LLM-discoverable via the binding API). When langchain_core
is missing, `@tool` is a no-op decorator -- the function is returned as-is.

This lets us smoke-test tool bodies before the langchain install lands,
without diverging the production interface.
"""
try:
    from langchain_core.tools import tool  # type: ignore[assignment]
except ImportError:
    def tool(fn):  # type: ignore[no-redef]
        return fn

__all__ = ["tool"]
