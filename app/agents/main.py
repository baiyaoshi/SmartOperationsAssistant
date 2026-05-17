import asyncio

from app.agents.graph import build_graph

graph = build_graph()
result = asyncio.run(graph.ainvoke({"message": ""}))
print(result["message"])