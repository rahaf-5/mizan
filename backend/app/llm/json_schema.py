"""Provider-neutral JSON Schema for structured LLM output.

Pydantic emits `$defs`/`$ref`; many providers handle inline schemas more
reliably, so references are inlined and unsupported keywords dropped.
Validation of the returned JSON is ALWAYS done again with the Pydantic model.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

_DROP = {"default", "title", "$defs", "examples", "minLength", "maxLength"}


def inline_schema(model: type[BaseModel]) -> dict[str, Any]:
    raw = model.model_json_schema()
    defs = raw.get("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                name = node["$ref"].split("/")[-1]
                return resolve(defs[name])
            return {k: resolve(v) for k, v in node.items() if k not in _DROP}
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node

    return resolve(raw)
