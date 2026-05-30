"""server._dispatcher — cohesion sub-package for dispatcher internals.

Extracted from server/dispatcher.py (T-OS3-DISPATCHER-REFACTOR).

Modules:
    prompt_builder  — ticket prompt assembly + orientation header + byte-budget
"""
from server._dispatcher.prompt_builder import PromptBuilder

__all__ = ["PromptBuilder"]
