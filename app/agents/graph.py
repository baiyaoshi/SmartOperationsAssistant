"""LangGraph Plan-Execute-Replan 演示"""

from typing import TypedDict, List
import json
from langgraph.graph import StateGraph, START, END

from app.core.llm import client
from app.runtime.agent_harness import get_agent_harness
from app.skills.registry import get_skill_registry
from app.tools.meta import tool_registry

from pydantic import BaseModel, Field
from app.core.structured import ainvoke_structured

harness = get_agent_harness()
registry = get_skill_registry()
menu = registry.to_router_menu()

class PlanExecuteState(TypedDict):
    input: str  # 用户原始问题
    selected_skill: str  # 选中的技能
    plan: List[str]  # 待执行的步骤列表
    past_steps: List[str]  # 已执行的步骤描述
    current_step: str  # 当前步骤
    current_result: str  # 当前步骤的结果
    response: str  # 最终报告
    step_index: int  # 当前步数
    is_finished: bool  # 是否完成

class SkillChoice(BaseModel):
    skill_name: str = Field(..., description=f"选中的技能名称，可选值: {', '.join(registry.names())}")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度 0~1")
    reason: str = Field(default="", description="选择原因")

class Plan(BaseModel):
    steps: List[str] = Field(
        ...,
        description="按顺序执行的步骤列表, 每步一句话",
    )

class ReplannerDecision(BaseModel):
    is_finished: bool = Field(..., description="诊断是否完成，true=生成报告，false=继续执行")
    plan: List[str] = Field(default_factory=list, description="剩余步骤，仅当 is_finished=false 时有值")
    response: str = Field(default="", description="最终报告，仅当 is_finished=true 时有值")

async def skill_router(state:PlanExecuteState)->dict:
    """判断用户提出问题属于哪一个诊断领域"""
    #加入了skill

    #注入prompt
    prompt = harness.skill_router_prompt.format(
        input=state["input"],
        menu=menu,
    )


    try:
        choice = await ainvoke_structured(
            llm=client,
            schema_cls=SkillChoice,
            messages=[{"role": "user", "content": prompt}],
            model_name=harness.router_model,
        )
        skill = choice.skill_name.strip().lower()
        print(f"选择了 Skill：{skill} (置信度: {choice.confidence}, 原因: {choice.reason})")
    except Exception as e:
        print(f"  skill_router LLM 调用失败，走默认值: {e}")
        skill = "generic"

    return {"selected_skill": skill}


#节点Planner（制定计划）
async def planner(state: PlanExecuteState) -> dict:
    """把用户问题拆成 2-3 个诊断步骤"""
    prompt = harness.planner_prompt.format(input=state["input"])

    try:
        plan = await ainvoke_structured(
            llm=client,
            schema_cls=Plan,
            messages=[{"role": "user", "content": prompt}],
            model_name=harness.planner_model,
        )
        steps = plan.steps
    except Exception as e:
        print(f"  planner LLM 调用失败，走默认计划: {e}")
        steps = ["收集系统基础信息", "分析异常指标", "汇总诊断结论"]

    print(f"计划: {steps}")
    return {"plan": steps, "step_index": 0, "is_finished": False}


#节点Executor（执行一步）
async def executor(state: PlanExecuteState) -> dict:
    """执行当前步骤"""
    idx = state["step_index"]
    step = state["plan"][idx]
    print(f" 执行第 {idx + 1} 步: {step}")

    #第一次调用，让llm决定是否要调用工具
    resp = await client.chat.completions.create(
        model=harness.executor_model,
        messages=[{"role": "user", "content": step}],
        tools=[info["definition"] for info in tool_registry.values()]
    )
    msg=resp.choices[0].message
    #如果决定调用工具
    if msg.tool_calls:
        tool_results=[]
        for tool_call in msg.tool_calls:
            tool_name=tool_call.function.name
            tool_info=tool_registry[tool_name]
            arguments=json.loads(tool_call.function.arguments)
            print(f"  → 调用工具: {tool_name}, 参数: {arguments}")
            result=tool_info["function"](**arguments)
            print(f"  ← 工具返回: {result}")
            tool_results.append({
                "role":"tool",
                "tool_call_id":tool_call.id,
                "content":result
            })
        #第二次调用，工具调用结果交给LLM
        second_resp=await client.chat.completions.create(
            model=harness.executor_model,
            messages=[
                {"role":"user","content":step},
                msg,
                *tool_results
            ]
        )
        result=second_resp.choices[0].message.content
    else:
        result=msg.content

    # 打开state 拼接过去完成步骤 拼接前50作为摘要后续我可能会进行修改
    new_past_steps = state.get("past_steps", []) + [f"{step} → {result}..."]
    return {
        "current_step": step,
        "current_result": result,
        "past_steps": new_past_steps,
        "step_index": idx + 1
    }


#节点Replanner（评估进度）
async def replanner(state: PlanExecuteState) -> dict:
    """评估进度，决定继续还是生成报告"""
    idx = state["step_index"]
    total = len(state["plan"])
    past_steps = state.get("past_steps", [])

    prompt = harness.replanner_prompt.format(
        input=state["input"],
        past_steps="\n".join(past_steps) if past_steps else "(暂无)",
    )

    try:
        decision = await ainvoke_structured(
            llm=client,
            schema_cls=ReplannerDecision,
            messages=[{"role": "user", "content": prompt}],
            model_name=harness.replanner_model,
        )

        if decision.is_finished:
            print(f" 报告生成完成")
            return {"response": decision.response, "is_finished": True}
        else:
            print(f" 还有 {len(decision.plan)} 步未执行，继续")
            return {"plan": decision.plan, "is_finished": False}

    except Exception as e:
        print(f"  replanner LLM 调用失败，走兜底: {e}")
        if idx >= total:
            # 兜底生成简单报告
            summary = "\n".join(past_steps) if past_steps else "未收集到有效信息"
            return {"response": f"诊断报告:\n{summary}", "is_finished": True}
        else:
            return {"is_finished": False}

#条件边: 判断是否继续
def should_continue(state: PlanExecuteState) -> str:
    if state["is_finished"]:
        return "end"
    else:
        return "continue"


#建图
def build_graph():
    builder = StateGraph(PlanExecuteState)
    builder.add_node("skill_router",skill_router)
    builder.add_node("planner", planner)
    builder.add_node("executor", executor)
    builder.add_node("replanner", replanner)

    builder.add_edge(START, "skill_router")
    builder.add_edge("skill_router","planner")
    builder.add_edge("planner", "executor")
    builder.add_edge("executor", "replanner")
    builder.add_conditional_edges(
        "replanner",
        should_continue,
        {
            "continue": "executor",  # 还有步骤 → 继续执行
            "end": END  # 完成 → 结束
        }
    )

    return builder.compile()