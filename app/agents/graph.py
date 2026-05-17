"""LangGraph Plan-Execute-Replan 演示"""

from typing import TypedDict, List
from langgraph.graph import StateGraph, START, END
from app.core.llm import client


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


async def skill_router(state:PlanExecuteState)->dict:
    """判断用户提出问题属于哪一个诊断领域"""
    prompt = f"""用户问题: {state['input']}
    请判断这是哪类问题, 从以下选项中选择一个:
    - host_resource: CPU/内存/磁盘/本机卡顿
    - network: ping/HTTP/DNS/端口/网址打不开
    - generic: 其他无法归类的故障
    只返回选项名称, 不要其他文字。"""
    resp=await client.chat.completions.create(
        model="qwen-plus",
        messages=[{"role":"user","content":prompt}]
    )
    skill=resp.choices[0].message.content.strip()
    print(f"选择了Skill：{skill}")
    return {"selected_skill":skill}


#节点Planner（制定计划）
async def planner(state: PlanExecuteState) -> dict:
    """把用户问题拆成 2-3 个诊断步骤"""
    prompt = f"""用户问题: {state['input']}
                请把这个问题拆成 2-3 个诊断步骤，每步一句话。
                只返回步骤列表，每行一个，不要序号。"""

    resp = await client.chat.completions.create(
        model="qwen-plus",
        messages=[{"role": "user", "content": prompt}]
    )
    steps = resp.choices[0].message.content.strip().split("\n")
    print(f"计划: {steps}")
    return {"plan": steps, "step_index": 0, "is_finished": False}


#节点Executor（执行一步）
async def executor(state: PlanExecuteState) -> dict:
    """执行当前步骤"""
    idx = state["step_index"]
    step = state["plan"][idx]
    print(f"🔧 执行第 {idx + 1} 步: {step}")

    #简单模拟让LLM回答这一步
    resp = await client.chat.completions.create(
        model="qwen-plus",
        messages=[{"role": "user", "content": f"请回答这个问题（模拟诊断工具）: {step}"}]
    )
    result = resp.choices[0].message.content

    # 打开state 拼接过去完成步骤 拼接前50作为摘要后续我可能会进行修改
    new_past_steps = state.get("past_steps", []) + [f"{step} → {result[:50]}..."]
    return {
        "current_step": step,
        "current_result": result,
        "past_steps": new_past_steps,
        "step_index": idx + 1
    }


#节点Replanner（评估进度）
async def replanner(state: PlanExecuteState) -> dict:
    """判断是否完成"""
    idx = state["step_index"]
    total = len(state["plan"])

    if idx >= total:
        # 所有步骤执行完毕，生成报告
        prompt = f"""用户问题: {state['input']}
                诊断记录: {state['past_steps']}
                请生成一份完整的诊断报告。"""
        resp = await client.chat.completions.create(
            model="qwen-plus",
            messages=[{"role": "user", "content": prompt}]
        )
        report = resp.choices[0].message.content
        print(f" 报告生成完成")
        return {"response": report, "is_finished": True}
    else:
        print(f" 还有 {total - idx} 步未执行，继续")
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