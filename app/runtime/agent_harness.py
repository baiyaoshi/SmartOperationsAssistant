"""AgentHarness — 控制面
把所有节点的 Prompt、模型选择、策略集中管理。
节点不再自己写 prompt，而是从 Harness 里取。
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class AgentHarness:
    """Agent 控制面：集中管理所有节点的 Prompt 和模型配置"""

    # 不同节点可以用不同模型（快/慢分离）
    router_model: str = "qwen-plus"      # SkillRouter 用
    planner_model: str = "qwen-plus"     # Planner 用
    executor_model: str = "qwen-plus"    # Executor 用
    replanner_model: str = "qwen-plus"   # Replanner 用

    # SkillRouter Prompt
    @property
    def skill_router_prompt(self) -> str:
        return """用户问题: {input}
            请从以下 Skill 菜单中选择一个最匹配的:
            {menu}
            请用 JSON 格式返回，包含以下字段:
            - skill_name: 选中的技能名称
            - confidence: 置信度 (0~1)
            - reason: 选择原因"""

    # Planner Prompt
    @property
    def planner_prompt(self) -> str:
        return """用户问题: {input}
                请把这个问题拆成 2-3 个诊断步骤，每步一句话。
                请用 JSON 格式返回，包含以下字段:
                - steps: 诊断步骤列表，每步一个字符串"""

    # Executor Prompt
    @property
    def executor_prompt(self) -> str:
        return """执行以下诊断步骤，如果需要可以调用工具。步骤: {step}"""

    # Replanner Prompt (生成报告)
    @property
    def replanner_prompt(self) -> str:
        return """用户问题: {input}
                已完成步骤: {past_steps}
                请判断诊断是否完成。
                如果还有步骤需要执行，返回剩余步骤列表。
                如果已完成，返回最终诊断报告。
                请用 JSON 格式返回，包含以下字段:
                - is_finished: true=完成生成报告，false=继续执行
                - plan: 剩余步骤列表（仅is_finished=false时有值）
                - response: 最终报告（仅is_finished=true时有值）"""


# 全局单例
_harness: AgentHarness | None = None


def get_agent_harness() -> AgentHarness:
    """获取全局 AgentHarness 单例"""
    global _harness
    if _harness is None:
        _harness = AgentHarness()
    return _harness


def set_agent_harness(harness: AgentHarness):
    """设置全局 AgentHarness（用于测试或动态配置）"""
    global _harness
    _harness = harness
