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
                请判断这是哪类问题, 从以下选项中选择一个:
                - host_resource: CPU/内存/磁盘/本机卡顿
                - network: ping/HTTP/DNS/端口/网址打不开
                - generic: 其他无法归类的故障
                只返回选项名称, 不要其他文字。"""

    # Planner Prompt
    @property
    def planner_prompt(self) -> str:
        return """用户问题: {input}
                请把这个问题拆成 2-3 个诊断步骤，每步一句话。
                只返回步骤列表，每行一个，不要序号。"""

    # Executor Prompt
    @property
    def executor_prompt(self) -> str:
        return """执行以下诊断步骤，如果需要可以调用工具。步骤: {step}"""

    # Replanner Prompt (生成报告)
    @property
    def replanner_report_prompt(self) -> str:
        return """用户问题: {input}
                诊断记录: {past_steps}
                请生成一份完整的诊断报告。"""


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
