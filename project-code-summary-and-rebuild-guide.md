# 项目代码总结与从零构建方案

> 多智能体 + RAG + Function Call 智能运维助手

---

## 一、项目一句话定性

这是一个 **基于 LangGraph 编排的多智能体 + RAG 知识库 + MCP 工具调用 的 AIOps 智能运维诊断平台**。

核心模式是 **Skill-first Plan-Execute-Replan 循环**：先判断故障类型选择 Skill，再制定诊断计划，然后调工具执行，最后评估进度，直到生成最终报告。

---

## 二、文件数量统计

```
核心代码文件     ~35 个  (app/ 目录下)
MCP 服务文件      ~5 个  (mcp_servers/)
前端文件          ~3 个  (frontend/)
配置文件          ~5 个  (requirements.txt, .env.example, docker-compose.yml, run.ps1, .gitignore)
文档/语料        ~若干   (docs/, data/kb_corpus/)
                 ------
总计             ~50+ 个文件 (不含语料数据)
```

---

## 三、完整目录结构（含每个文件含义）

```
multirag-agent/                          # 项目根目录
│
├── app/                                  # ★ 核心应用代码 (Python)
│   ├── main.py                           #   FastAPI 应用入口, 启动/关闭钩子, 路由注册, 异常处理器
│   ├── config.py                         #   Pydantic Settings 配置管理 (.env → 类型安全配置, 单例)
│   ├── exceptions.py                     #   全局业务异常定义 (AppException)
│   ├── logging_config.py                 #   日志配置 (loguru)
│   │
│   ├── agents/                           # ★ 多智能体核心 — LangGraph 图编排 (L1)
│   │   ├── graph.py                      #     LangGraph 图定义: 4 个节点 + 条件边
│   │   │                                  #     skill_router → planner → executor → replanner
│   │   │                                  #     节点之间通过 conditional_edges 形成循环
│   │   ├── state.py                      #     PlanExecuteState (TypedDict): 图的状态定义
│   │   │                                  #     input/selected_skill/plan/past_steps/response 等
│   │   ├── skill_router.py               #     LLM 节点 1: 判断是否 OnCall, 从菜单选 Skill
│   │   │                                  #     双层兜底: LLM 失败 → 规则关键词匹配
│   │   ├── planner.py                    #     LLM 节点 2: 基于 Skill Playbook 拆诊断计划
│   │   │                                  #     输出 Plan.steps (Pydantic 结构化)
│   │   ├── executor.py                   #     LLM 节点 3: 执行计划中的一步, 调用工具
│   │   │                                  #     支持并行/串行两种模式, 按 Skill 过滤工具
│   │   ├── replanner.py                  #     LLM 节点 4: 评估进度, 决定收尾/继续/reroute
│   │   │                                  #     三层防死循环 + 自动收敛 + 报告合成
│   │   ├── fork_runner.py                #     §4: 独立子图 (Fork Skill) 入口
│   │   │                                  #     子图复用主图, 通过 inside_fork 标记防递归
│   │   ├── stream_sink.py                #     SSE 事件流: ContextVar + asyncio.Queue
│   │   │                                  #     把 Executor 内部的 token 旁路到 API 层
│   │   └── subagents/                    #     §5: 二级 Agent 委托 (包装成 BaseTool)
│   │       ├── __init__.py               #       SubagentDefinition 数据模型 + 3 个内置 Agent 定义
│   │       └── runner.py                 #       包装成 delegate_to_* 工具, 主 Executor 可调用
│   │
│   ├── runtime/                          # ★ 运行时引擎 — 控制面 + 编排 + 权限
│   │   ├── agent_harness.py              #     AgentHarness 控制面: 所有 Prompt/模型/策略
│   │   │                                  #     8 套 Prompt + 模型选择 + 预算管理 + 降级
│   │   ├── tool_runner.py                #     §3: 并行编排引擎 (partition + gather + 异常隔离)
│   │   │                                  #     按 concurrency_safe 切批, 读工具并行, 写串行
│   │   ├── tool_filter.py                #     工具三层过滤: Skill 白名单 → Mode → Guardrails
│   │   │                                  #     输出 visible_tools + PermissionDecision dict
│   │   ├── permissions.py                #     §1: 权限决策 (PermissionMode + PermissionDecision)
│   │   │                                  #     4 种 Mode + 三态决策 (allow/ask/deny)
│   │   └── transitions.py               #     §6: 转换原因枚举 + StateTransition 结构
│   │                                      #     每个节点出口打一个原因, 形成可观测时间线
│   │
│   ├── tools/                            # ★ 工具层 — 元数据 + 注册 + 加载
│   │   ├── meta.py                       #     ToolMeta 中央注册表: 每个工具的语义声明
│   │   │                                  #     read_only/concurrency_safe/risk_level/max_result_chars
│   │   ├── mcp_loader.py                 #     MCP 工具加载器: 本地工具 + MCP 工具合并
│   │   │                                  #     同名去重: 本地优先
│   │   ├── knowledge_tool.py             #     知识库搜索工具 (search_knowledge_base)
│   │   ├── time_tool.py                  #     获取当前时间工具 (get_current_time)
│   │   ├── system_tool.py                #     本机系统 @tool (psutil wrapper)
│   │   │                                  #     get_local_* / list_top_processes
│   │   └── lazy_mcp_tools.py             #     MCP 两阶段发现/执行 (mcp_search_tools/mcp_execute_tool)
│   │
│   ├── skills/                           # ★ Skill 体系 — 故障域专家定义 (L2)
│   │   ├── models.py                     #     Skill 数据模型 (Pydantic)
│   │   ├── loader.py                     #     SKILL.md 解析器 (YAML frontmatter + Markdown body)
│   │   ├── registry.py                   #     SkillRegistry 全局单例
│   │   └── definitions/                  #     每个 Skill 一个文件夹
│   │       ├── host_resource_diagnosis/  #       CPU/内存/磁盘/本机卡顿
│   │       │   └── SKILL.md
│   │       ├── network_diagnosis/        #       ping/HTTP/DNS/端口
│   │       │   └── SKILL.md
│   │       ├── container_diagnosis/      #       Docker 容器诊断
│   │       │   └── SKILL.md
│   │       └── generic_oncall/           #       通用兜底
│   │           └── SKILL.md
│   │
│   ├── core/                             # 基础设施层
│   │   ├── llm.py                        #   LLM 工厂: DashScope, DeepSeek, Ollama 三选一
│   │   ├── llm_health.py                 #   LLM 健康探测 (TCP 连通性)
│   │   ├── structured.py                 #   结构化输出兼容层 (JSON 解析 + Pydantic 校验)
│   │   ├── milvus.py                     #   Milvus 向量数据库连接管理
│   │   ├── embedding.py                  #   Embedding 模型 (text-embedding-v4)
│   │   ├── vector_store.py               #   向量存储 CRUD
│   │   ├── hybrid_retriever.py           #   Hybrid Search (BM25 + Vector + RRF)
│   │   ├── reranker.py                   #   Reranker (gte-rerank-v2)
│   │   ├── mcp_client.py                 #   MCP 客户端管理 (多 server 连接/断开)
│   │   └── web_search.py                #   联网搜索 (open-webSearch / mock / ddgs)
│   │
│   ├── services/                         # 业务服务层
│   │   ├── aiops_service.py              #   AIOps 诊断服务: 编排 LangGraph 图, 产出 SSE 事件流
│   │   ├── rag_service.py                #   RAG 聊天服务: 检索 + 联网 + 工具 + LLM 流式
│   │   ├── document_service.py           #   文档管理: 上传/分块/入库/删除
│   │   └── chat_memory.py                #   会话记忆存储 (Redis)
│   │   └── rag/                          #   RAG 子模块
│   │       ├── retrieval.py              #     知识库检索逻辑
│   │       ├── memory.py                 #     会话记忆 (改写/压缩)
│   │       └── web_context.py            #     联网搜索上下文
│   │
│   ├── api/v1/                           # HTTP API 路由
│   │   ├── health.py                     #   健康检查 (liveness/readiness)
│   │   ├── aiops.py                      #   POST /aiops/diagnose (SSE 流式诊断)
│   │   ├── chat.py                       #   POST /chat/stream (SSE 流式聊天)
│   │   ├── documents.py                  #   CRUD /documents (知识库管理)
│   │   ├── skills.py                     #   GET /skills (Skill 列表)
│   │   └── webhook.py                    #   POST /webhook/alertmanager
│   │
│   ├── schemas/                          # Pydantic 数据模式
│   │   ├── common.py                     #   通用响应 (ApiResponse)
│   │   ├── aiops.py                      #   诊断请求/响应
│   │   ├── chat.py                       #   聊天请求/响应
│   │   └── document.py                   #   文档请求/响应
│   │
│   ├── api/                              # API 基础设施
│   │   ├── middleware.py                 #   CORS/日志/请求 ID 中间件
│   │   └── __init__.py
│   │
│   └── utils/                            # 工具函数
│       └── splitter.py                   # 文档分块器
│
├── mcp_servers/                          # MCP 远程服务端 (独立进程, FastMCP)
│   ├── system_server.py                  #   本机系统 MCP: psutil (CPU/内存/磁盘/进程)
│   ├── network_server.py                 #   网络诊断 MCP: ping/HTTP/DNS/端口
│   ├── docker_server.py                  #   Docker 管理 MCP: ps/stats/logs/inspect/restart
│   ├── winlog_server.py                  #   Windows 事件日志 MCP
│   └── websearch_server.py              #   联网搜索 MCP (调用 open-webSearch daemon)
│
├── frontend/                             # Web 前端 (纯 HTML + TailwindCSS + Vanilla JS)
│   ├── index.html                        #   入口页面
│   ├── styles.css                        #   样式
│   └── app.js                           #   前端逻辑: 调用 API + SSE 展示
│
├── data/kb_corpus/                       # 知识库语料
│   └── awesome-prometheus-alerts/        #   samber/awesome-prometheus-alerts (CC BY 4.0)
│       └── *.md                          #     954 个 Prometheus 告警规则文档
│
├── docs/                                 # 项目文档
│   ├── README.md                         #   中文导读
│   ├── sop/                              #   SOP 文档
│   └── ...                               #   更多文档
│
├── scripts/                              # 工具脚本
│   ├── ingest_kb_corpus.py               #   知识库导入脚本
│   ├── fetch_kb_corpus.ps1               #   语料下载脚本
│   ├── mock_alert.py                     #   Alertmanager Webhook 模拟
│   └── convert_prometheus_alerts.py      #   告警语料格式转换
│
├── .env.example                          # 环境变量模板
├── requirements.txt                      # Python 依赖
├── run.ps1                               # Windows 一键启动脚本
├── docker-compose.yml                    # Docker 编排 (Milvus + etcd + minio + Redis + open-webSearch)
└── README.md                             # 项目英文 README
```

---

## 四、核心架构: 4 层多智能体

这个项目的多智能体不是"多个 LLM 聊天"，而是 4 种不同粒度的多智能体嵌套。

| 层次 | 名称 | 文件 | 本质 | 类比 |
|------|------|------|------|------|
| **L1** | Graph Nodes | `agents/graph.py` | 4 个 LLM 节点协作完成一次诊断 | 团队流水线分工 |
| **L2** | Skill Router | `agents/skill_router.py` | 按问题类型选择不同的"专家" Skill | 接线员分发给专长工程师 |
| **L3** | Fork Runner | `agents/fork_runner.py` | 整个子图作为独立 Agent 执行 | 外包团队干活, 只汇报结果 |
| **L4** | Subagent | `agents/subagents/runner.py` | 把二级 Agent 包装成工具 | 工程师喊实习生查资料 |

### L1: Graph Node (主图) — 最核心

```text
用户输入 → SkillRouter(选方向) → Planner(定计划) → Executor(调工具) → Replanner(评估)
  ↑                                                                         │
  └────────────────────── 继续/reroute ──────────────────────────────────────┘
                                                                             ↓
                                                                          END(报告)
```

每个节点使用不同的 LLM 实例、不同的 System Prompt、不同的工具集：

| 节点 | 推荐模型 | 工具 | 职责 |
|------|---------|------|------|
| SkillRouter | 快模型 (turbo) | 无 | 仅做路由决策 |
| Planner | 快模型 (turbo) | 无 | 仅做计划生成 |
| Executor | 最快模型 (flash) | 全工具 | 仅执行当前步骤 |
| Replanner | 快模型决策 + 强模型写报告 | 无 | 仅评估进度 |

### L2: Skill Router (故障域路由)

```python
# 示例: 用户输入 → 选哪个 Skill?
"我的电脑好卡"        → host_resource_diagnosis
"网址打不开"           → network_diagnosis
"Docker 容器挂了"     → container_diagnosis
其他无法归类的故障     → generic_oncall
```

每个 Skill 定义一套独立的 **Playbook (SOP)** + **工具白名单** + **风险等级**。

### L3: Fork Runner (独立子图)

Skill 标记为 `context: fork` 时, 跑一个完整的 Plan-Execute-Replan 子图：

```
主图 → fork_skill_node
         ├── 构建子图 input
         ├── 子图 = build_aiops_graph() (复用主图结构)
         │     └── inside_fork=True 防止无限递归
         └── 子图 response → 主图 response → END
```

### L4: Subagent (工具级委托)

主 Executor 看到 3 个特殊的工具名，调用它们等于启动一个子 Agent：

| 工具名 | 职责 | 内部工具池 |
|--------|------|-----------|
| `delegate_to_evidence_collector` | 收集指标/日志/进程 | psutil, 事件日志等 |
| `delegate_to_kb_researcher` | 查知识库/联网搜索 | search_knowledge_base, web_search |
| `delegate_to_report_writer` | 写最终报告 | 无工具, 纯 LLM |

---

## 五、数据流全景

```text
用户输入
   │
   ├──→ AIOps 诊断 (/api/v1/aiops/diagnose)
   │      ├── aiops_service.stream_diagnose()
   │      │     └── agent.graph.ainvoke()
   │      │           ├── skill_router → 选 Skill (L2)
   │      │           ├── planner → 拆 2-3 步
   │      │           ├── executor → 调 MCP 工具 (L4 可委托 Subagent)
   │      │           │     ├── system_server (psutil CPU/内存/磁盘)
   │      │           │     ├── network_server (ping/HTTP/DNS)
   │      │           │     ├── docker_server (容器 stats/logs)
   │      │           │     ├── winlog_server (事件日志)
   │      │           │     └── delegate_to_* (Subagent 委托)
   │      │           └── replanner → 评估/reroute/收尾
   │      └── SSE 流推送 (step_start / step_token / tool_call / report)
   │
   └──→ RAG 聊天 (/api/v1/chat/message)
          ├── rag_service.achat()
          │     ├── Query Rewrite (融合历史)
          │     ├── 知识库检索 (Milvus + Hybrid Search + Reranker)
          │     ├── 联网搜索 (可选)
          │     ├── MCP 工具 (只读, 按需)
          │     └── LLM 生成 (流式)
          └── SSE 流推送 (token / sources / usage)
```

---

## 六、6 个核心设计模式 (cc-haha 借鉴)

以下是项目从 cc-haha (Claude Code Harness) 借鉴的 6 个关键模式：

### §1 PermissionMode — 三层权限防御

- **4 种 Mode**: `read_only` / `normal` / `ask_destructive` / `bypass`
- **3 态决策**: `allow` (允许) / `ask` (需审批) / `deny` (拒绝)
- **决策链**: Skill 白名单 → Mode 限制 → Guardrails 黑名单

### §2 ToolMeta — 工具元数据注册

每个工具声明 read_only / concurrency_safe / risk_level / max_result_chars
未登记的工具按保守默认处理 (fail-closed)

### §3 并行编排 — read-only 工具 gather 执行

- 用 `concurrency_safe` 分类工具
- 相邻 safe 工具合批 async gather
- 异常隔离: 一个工具失败不影响兄弟

### §4 Fork — 独立子图

Skill 标记 `context: fork` 时跑完整子图，上下文隔离 + token 预算独立

### §5 Subagent — 二级 Agent 委托

把二级 Agent 包装成 BaseTool，主 Executor 通过工具调用委托任务

### §6 Transition — 结构化可观测性

每个节点出口打一个结构化的原因枚举，形成可按 grep 排查的时间线

---

## 七、各层依赖关系

```
api/v1/*                             HTTP API
  └── services/                      业务编排
        ├── agents/graph.py          多智能体图编排
        │     ├── agents/            4 个 LLM 节点
        │     ├── runtime/           控制面 + 编排 + 权限
        │     ├── skills/            Skill 定义
        │     └── core/              LLM 工厂 + 向量库
        │
        ├── services/rag/            RAG 子模块
        │     └── core/              Embedding + Hybrid Search + Milvus
        │
        └── tools/                   工具元数据注册

core/*                               基础设施 (无上层依赖)
tools/meta.py                        工具元数据 (无上层依赖)
skills/                              依赖 core/llm
runtime/                             依赖 tools/meta + skills
agents/                              依赖 runtime + skills + core
services/                            依赖 agents + core
api/                                 依赖 services
```

---

## 八、从零构建方案 (5 阶段逐步演化)

> 每个阶段产物可独立运行, 按 Skill priority 逐步加入复杂度。

### 阶段 1: 最小骨架 (Week 1) — 跑通 HTTP + LLM

**目标**: FastAPI 启动, 能调一次 LLM, 返回 JSON。

```
my_agent/
├── app/
│   ├── main.py              ← FastAPI app + lifespan
│   ├── config.py             ← Pydantic Settings (.env)
│   ├── core/
│   │   ├── __init__.py
│   │   └── llm.py            ← LLM 工厂 (先只支持一种 provider)
│   └── api/
│       ├── __init__.py
│       └── v1/
│           ├── __init__.py
│           └── health.py     ← GET /api/v1/health
├── requirements.txt          ← fastapi, uvicorn, pydantic-settings, openai
├── .env.example
└── run.sh
```

**验证**: `curl http://localhost:9900/api/v1/health` 返回 `{"status":"ok"}`

| 新增文件数 | 依赖包数 | 外部依赖 |
|-----------|---------|---------|
| ~6 个 | ~5 个 | 无 |

---

### 阶段 2: 单 Agent + 工具 (Week 2-3) — 能对话 + 能调工具

**目标**: 用 `create_agent` 做一个能调 MCP 工具的普通 Agent, 可回答"我的电脑 CPU 怎么样?"

```
my_agent/
├── app/
│   ├── (继承阶段 1 )
│   ├── core/
│   │   ├── mcp_client.py     ← MCP 客户端管理 (连接/断开)
│   │   └── structured.py     ← JSON 结构化输出兼容层
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── meta.py            ← ToolMeta 注册中心 (建立基础)
│   │   ├── mcp_loader.py      ← 本地 + MCP 工具合并
│   │   ├── time_tool.py       ← 本地 @tool: get_current_time
│   │   └── system_tool.py     ← 本地 @tool: psutil 本机
│   ├── agents/
│   │   └── simple_agent.py    ← create_agent 版本 (先不用 graph)
│   └── api/v1/
│       └── chat.py            ← POST /api/v1/chat/stream (SSE)
├── mcp_servers/
│   └── system_server.py       ← psutil MCP (FastMCP)
└── frontend/
    └── index.html              ← 简易聊天界面
```

**关键建立**: 必须在这个阶段建好 `tools/meta.py` 的基础结构，否则后面改 ToolMeta 会涉及大面积重构。

**验证**: `POST /api/v1/chat/stream` 回答"我的电脑CPU使用率多少"，前端 SSE 展示文字。

| 新增文件数 | 依赖包数 | 外部依赖 |
|-----------|---------|---------|
| ~15 个 | + langchain, langchain-openai, fastmcp | MCP server (本机) |

---

### 阶段 3: Skill-first + LangGraph 多智能体 (Week 4-5) — 核心价值

**目标**: 引入 Skill-first 路由 + Plan-Execute-Replan 循环, 替代单 Agent。这是整个项目的核心价值所在。

```
my_agent/
├── app/
│   ├── (继承阶段 2 )
│   ├── agents/
│   │   ├── graph.py           ← LangGraph StateGraph 定义
│   │   ├── state.py           ← PlanExecuteState (TypedDict)
│   │   ├── skill_router.py    ← 路由节点 (Pydantic 结构化输出)
│   │   ├── planner.py          ← 计划节点 (基于 Playbook)
│   │   ├── executor.py         ← 执行节点 (调工具)
│   │   └── replanner.py        ← 评估节点 (收尾/继续/reroute)
│   ├── runtime/
│   │   ├── __init__.py
│   │   ├── agent_harness.py   ← ★ 必须在此阶段引入:
│   │   │                         把所有 Prompt/模型/策略集中管理
│   │   └── transitions.py     ← 原因枚举 (可观测性)
│   ├── skills/
│   │   ├── __init__.py
│   │   ├── models.py          ← Skill 数据模型
│   │   ├── loader.py          ← SKILL.md 解析
│   │   ├── registry.py        ← 注册表
│   │   └── definitions/       ← 2-3 个 Skill
│   │       ├── host_resource_diagnosis/SKILL.md
│   │       ├── network_diagnosis/SKILL.md
│   │       └── generic_oncall/SKILL.md
│   └── api/v1/
│       └── aiops.py           ← POST /api/v1/aiops/diagnose (SSE)
└── frontend/
    ├── index.html              ← 完整诊断面板
    ├── styles.css
    └── app.js                 ← SSE 事件解析 + 渲染
```

**关键要点**:
- `agent_harness.py` 必须在阶段 3 引入, 否则 Prompt 散落到各节点文件里难以维护
- 先写 2-3 个 Skill 即可, 后面再扩充
- SSE 流式是必选项 (用户等待诊断时需要看到进度)

**验证**: `POST /api/v1/aiops/diagnose` 对"我的电脑很卡" 输出 SSE 流:
`start → skill_selected → plan → step_complete → ... → report → complete`

| 新增文件数 | 依赖包数 | 外部依赖 |
|-----------|---------|---------|
| ~30 个 | + langgraph, loguru | 无 (纯文本模式即可运行) |

---

### 阶段 4: RAG 知识库 + Milvus (Week 6-7) — 知识增强

**目标**: 接入向量数据库, 让 Agent 诊断时能查知识库, 同时增加 RAG 聊天功能。

```
my_agent/
├── app/
│   ├── (继承阶段 3 )
│   ├── core/
│   │   ├── milvus.py          ← Milvus 连接管理
│   │   ├── embedding.py       ← Embedding 封装
│   │   ├── vector_store.py    ← 向量 CRUD
│   │   ├── hybrid_retriever.py ← BM25 + Vector + RRF
│   │   └── reranker.py        ← Reranker
│   ├── tools/
│   │   └── knowledge_tool.py  ← search_knowledge_base
│   ├── services/
│   │   ├── rag_service.py     ← RAG 聊天服务 (SSE)
│   │   ├── document_service.py ← 文档上传/分块/入库
│   │   └── chat_memory.py     ← Redis 会话记忆
│   ├── services/rag/
│   │   ├── retrieval.py       ← 检索逻辑
│   │   ├── memory.py          ← 会话改写/压缩
│   │   └── web_context.py     ← 联网搜索上下文
│   └── api/v1/
│       ├── documents.py       ← 知识库管理 API
│       ├── skills.py          ← Skill 管理 API
│       └── webhook.py         ← Alertmanager Webhook
├── docker-compose.yml         ← Milvus + etcd + minio + Redis
├── scripts/
│   ├── ingest_kb_corpus.py    ← 知识库导入
│   └── fetch_kb_corpus.ps1    ← 语料下载
└── data/kb_corpus/            ← 语料目录
```

**注意**: AgentHarness 的 Prompt 集合要从阶段 3 的基础版本扩展到包含 RAG Prompt、
Rewrite Prompt、Compact Prompt。

**验证**:
1. 上传文档 → 知识库可用
2. RAG 聊天"Redis 内存满了怎么排查"→ 命中知识库
3. 诊断时自动搜知识库

| 新增文件数 | 依赖包数 | 外部依赖 |
|-----------|---------|---------|
| ~40 个 | + pymilvus, langchain-milvus, redis | Milvus + Redis (Docker) |

---

### 阶段 5: 进阶功能 (Week 8+) — 生产级特性

**目标**: 补全所有进阶特性和安全控制。

```
my_agent/
├── app/
│   ├── (继承阶段 4 )
│   ├── agents/
│   │   ├── fork_runner.py     ← §4: Fork 独立子图
│   │   ├── stream_sink.py     ← SSE 事件旁路
│   │   └── subagents/         ← §5: 二级 Agent
│   │       ├── __init__.py    ← 3 个 Subagent 定义
│   │       └── runner.py      ← 包装成 BaseTool
│   ├── runtime/
│   │   ├── tool_runner.py     ← §3: 并行编排引擎
│   │   ├── tool_filter.py     ← 三层过滤
│   │   └── permissions.py     ← §1: 权限决策
│   ├── mcp_servers/           ← 扩充 MCP 服务
│   │   ├── network_server.py
│   │   ├── docker_server.py
│   │   ├── winlog_server.py
│   │   └── websearch_server.py
│   ├── api/v1/
│   │   └── webhook.py         ← Alertmanager Webhook
│   └── schemas/               ← 完整 Pydantic 模式
├── frontend/                  ← 完整 UI
└── docs/                      ← 完整文档
```

**验证**: 完整 UI + 4 个 MCP 服务 + 并行工具 + 权限控制 + Webhook 接入。

| 新增文件数 | 依赖包数 | 外部依赖 |
|-----------|---------|---------|
| ~50 个 | + numpy, psutil | 全部 |

---

## 九、阶段依赖图

```
阶段 1: FastAPI 骨架 (5 个文件)
  │
  ▼
阶段 2: 单 Agent + MCP 工具 (15 个文件)
  │    ← 从这里开始可独立演示"问答 + 调工具"
  │    ← 建立 ToolMeta 注册的基础
  │
  ▼
阶段 3: LangGraph 多智能体图 (30 个文件)
  │    ← 核心价值: Skill-first 诊断流程
  │    ← 必须引入 AgentHarness 控制面
  │    ← 纯文本模式即可运行 (无需数据库)
  │
  ├──→ 阶段 3.5: SSE 流式前端 (可选子步骤)
  │
  ▼
阶段 4: RAG + Milvus (40 个文件)
  │    ← 需要 Docker 跑 Milvus + Redis
  │    ← AgentHarness 扩展 RAG Prompt
  │
  ▼
阶段 5: 进阶功能 (50+ 个文件)
       ← 并行编排 / 权限 / Subagent / Fork / Webhook
```

### 每阶段核心风险与应对

| 阶段 | 最大风险 | 应对 |
|------|---------|------|
| 1 | LLM 配置复杂 | 先写死一个 provider, 后面再抽象工厂 |
| 2 | MCP 协议学习曲线 | 先写本地 @tool, MCP 通过 HTTP 调用 |
| 3 | LangGraph 调试困难 | 先写单步测试, 图复杂了加断点 |
| 4 | Milvus 连接失败 | 用 `fail_silently` 降级为无向量搜索 |
| 5 | 功能膨胀 | 阶段 5 可拆分多个小阶段按需交付 |

---

## 十、必须一开始建立的核心基础设施

| # | 组件 | 引入阶段 | 为什么不能拖 |
|---|------|---------|------------|
| 1 | `core/llm.py` | 阶段 1 | 所有节点都依赖 LLM, 后面改 factory 代价大 |
| 2 | `core/structured.py` | 阶段 2 | Pydantic 结构化输出兼容层, 后面换模型也不怕 |
| 3 | `tools/meta.py` | 阶段 2 | 每个工具都要声明, 后面补登记遗漏率高 |
| 4 | `runtime/agent_harness.py` | 阶段 3 | 阶段 3 有 4 个节点, 没有 Harness Prompt 散落一地 |
| 5 | `runtime/transitions.py` | 阶段 3 | 从第 1 个节点开始就打 transition, 后面才能追溯 |

---

## 十一、代码量估算

| 阶段 | Python 代码行数 (估算) | JS/CSS 行数 | 配置文件行数 |
|------|----------------------|------------|------------|
| 1 | ~200 | 0 | ~50 |
| 2 | ~800 | ~200 | ~80 |
| 3 | ~2500 | ~500 | ~100 |
| 4 | ~4000 | ~500 | ~150 |
| 5 | ~5500 | ~800 | ~200 |

> 注意: 以上不含语料数据文件和第三方代码。实际项目从零开始写代码大约 5500 行 Python。

---

## 十二、一句话总结构建顺序

```
1. 跑通 FastAPI + 调一次 LLM
2. 加工具 (先本地, 再 MCP), 注册到 ToolMeta
3. 引入 AgentHarness 控制面 + LangGraph 多 Agent 图
4. 加 RAG (Milvus + Embedding + Hybrid Search)
5. 加进阶: 并行编排 / 权限 / Subagent / Fork
```
