"""转换原因枚举 — 每个节点出口打一个结构化的原因标签

每个节点执行完后，在 return 里附带 transition_reason 字段，
方便排查图执行的决策链路。
"""

from enum import Enum


class NodeTransition(str, Enum):
    """每个节点的出口原因"""

    # ── SkillRouter ──
    SKILL_MATCHED = "skill_matched"          # LLM 成功匹配到技能
    SKILL_FALLBACK = "skill_fallback"        # LLM 失败，走规则/兜底
    SKILL_AMBIGUOUS = "skill_ambiguous"      # LLM 返回了非法技能名

    # ── Planner ──
    PLAN_GENERATED = "plan_generated"        # 计划生成成功
    PLAN_FALLBACK = "plan_fallback"          # LLM 失败，走默认计划

    # ── Executor ──
    STEP_COMPLETED = "step_completed"        # 步骤执行完成（LLM 直接回答）
    TOOL_CALLED = "tool_called"              # 步骤中调用了工具
    TOOL_FAILED = "tool_failed"              # 工具调用异常

    # ── Replanner ──
    FINISHED = "finished"                    # 诊断完成，生成报告
    NEED_MORE_STEPS = "need_more_steps"      # 还需要更多步骤
    REROUTE = "reroute"                      # 需要切换诊断方向
    FORCE_FINISH = "force_finish"            # 防死循环强制结束
    REPLANNER_FALLBACK = "replanner_fallback"  # LLM 失败，兜底处理