"""Skill 数据模型 — 每个 Skill 由一个 SKILL.md 文件描述"""

from typing import List, Optional
from pydantic import BaseModel, Field


class Skill(BaseModel):
    """单个 Skill 的运行时表示"""

    name: str = Field(..., description="Skill 唯一标识, snake_case, 例如 host_resource_diagnosis")
    display_name: str = Field(..., description="人类可读名称")
    description: str = Field(..., description="适用场景一句话描述")
    triggers: List[str] = Field(default_factory=list, description="触发关键字")
    allowed_tools: List[str] = Field(default_factory=list, description="允许的工具白名单，空=全部允许")
    risk_level: str = Field(default="low", description="风险等级: low/medium/high")

    # Markdown body
    playbook: str = Field(default="", description="完整 Markdown 正文")
    source_path: Optional[str] = Field(default=None, description="源 SKILL.md 文件路径")

    def to_router_card(self) -> str:
        """生成给 Router LLM 看的菜单条目"""
        triggers = ", ".join(self.triggers) if self.triggers else "(无)"
        return (
            f"- **{self.name}** — {self.display_name}\n"
            f"  适用场景: {self.description}\n"
            f"  触发关键字: {triggers}"
        )