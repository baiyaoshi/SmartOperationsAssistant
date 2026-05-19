"""结构化输出兼容层 — 让 LLM 返回 JSON，解析成 Pydantic 对象"""

import json
import re
from typing import Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def _schema_hint(schema_cls: Type[BaseModel]) -> str:
    """把 Pydantic 模型转换成 JSON 字段说明文本，塞给 LLM"""
    schema = schema_cls.model_json_schema()
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    lines = []
    for name, meta in props.items():
        type_name = meta.get("type") or "any"
        req = "必填" if name in required else "可选"
        desc = meta.get("description", "")
        lines.append(f'  - "{name}" ({req}, {type_name}): {desc}')
    return "\n".join(lines)


def _extract_json(text: str) -> dict:
    """从 LLM 回复中提取 JSON 对象（兼容 ```json 代码块）"""
    raw = text.strip()
    # 去掉 markdown 代码块标记
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # 如果整段不是 JSON，尝试从中提取 {...}
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not match:
            raise ValueError(f"无法从 LLM 回复中提取 JSON: {text[:200]}")
        return json.loads(match.group(0))

async def ainvoke_structured(
    *,
    llm,
    schema_cls: Type[T],
    messages: list[dict],
    model_name: str,
) -> T:
    # 构造 system prompt：告诉 LLM 输出 JSON 格式
    json_instruction = {
        "role": "system",
        "content": (
            "你必须只输出一个合法的 json 对象 (严格 json 格式，小写 json)，"
            "不要 markdown，不要代码块，不要解释。\n"
            "json 字段要求:\n"
            f"{_schema_hint(schema_cls)}"
        ),
    }

    resp = await llm.chat.completions.create(
        model=model_name,
        messages=[json_instruction, *messages],
        response_format={"type": "json_object"},
    )
    text = resp.choices[0].message.content
    data = _extract_json(text)
    print(f"  [structured] 原始 JSON: {data}")
    obj = schema_cls.model_validate(data)
    return obj