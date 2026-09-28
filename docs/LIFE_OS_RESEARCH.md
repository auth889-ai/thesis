# LIFE OS — research foundation and architecture map

A personal agent that completes everyday workflows (email, calendar, tasks, files, mobility, travel) under the user's
permission. This document names the research each component stands on, pins the official code at a commit
(`docs/life_os_pins.json`, pinned 2026-09-28), and states what is reused verbatim, what is adapted, and what is original.
The mobility module is the existing TrafficTwin system (forecasting, routing, digital twin); the rest is new.

## Architecture and its papers

```
user goal → understand context (memory) → plan (agent loop) → use tools (connectors, MCP) → act (permission engine) → track (audit log, workflows) → adapt (reflection)
```

| component | what it does | paper / standard | official code (pinned) | reuse |
|---|---|---|---|---|
| **Agent orchestrator** | the think–act–observe loop that drives every workflow | ReAct: Synergizing Reasoning and Acting in Language Models — Yao, S., Zhao, J., Yu, D., Du, N., Shafran, I., Narasimhan, K., Cao, Y., *ICLR 2023*, arXiv:2210.03629 | [ysymyth/ReAct](https://github.com/ysymyth/ReAct) @ `6bdb3a1fd38b` | adapt: our loop is a typed re-implementation with the paper's prompt structure |
| **Adaptation** | after a failed or corrected workflow, write a verbal reflection into memory and retry with it in context | Reflexion: Language Agents with Verbal Reinforcement Learning — Shinn, N., Cassano, F., Gopinath, A., Narasimhan, K., Yao, S., *NeurIPS 2023*, arXiv:2303.11366 | [noahshinn/reflexion](https://github.com/noahshinn/reflexion) @ `218cf0ef1df8` | adapt |
| **User memory** | observation stream + retrieval by recency, importance, relevance + periodic reflection | Generative Agents: Interactive Simulacra of Human Behavior — Park, J. S., O'Brien, J. C., Cai, C. J., Morris, M. R., Liang, P., Bernstein, M. S., *UIST 2023*, arXiv:2304.03442 | [joonspk-research/generative_agents](https://github.com/joonspk-research/generative_agents) @ `fe05a71d3e4e` | adapt (retrieval scoring taken verbatim) |
| **Long-term context** | tiered memory the model manages itself (core vs archival), paging facts in and out | MemGPT: Towards LLMs as Operating Systems — Packer, C., Wooders, S., Lin, K., Fang, V., Patil, S. G., Stoica, I., Gonzalez, J. E., *arXiv 2023*, arXiv:2310.08560 | [letta-ai/letta](https://github.com/letta-ai/letta) @ `5bcdd177d70f` | adapt (paging policy) |
| **Connectors** | Gmail, Calendar, files, maps, tasks exposed as MCP servers behind one tool interface | Model Context Protocol (specification) — Anthropic and contributors, *open standard*, https://modelcontextprotocol.io/ | [modelcontextprotocol/modelcontextprotocol](https://github.com/modelcontextprotocol/modelcontextprotocol) @ `ab3a39c13bd2` | reuse the spec and reference SDK |
| **Connector evaluation** | does the agent call the right API with the right arguments | ToolLLM: Facilitating Large Language Models to Master 16000+ Real-world APIs — Qin, Y., et al., *ICLR 2024*, arXiv:2307.16789 | [OpenBMB/ToolBench](https://github.com/OpenBMB/ToolBench) @ `d56fdd89faf8` | reuse evaluation protocol |
| **Function-call scoring** | Berkeley Function Calling Leaderboard metrics for argument correctness | Gorilla: Large Language Model Connected with Massive APIs — Patil, S. G., Zhang, T., Wang, X., Gonzalez, J. E., *NeurIPS 2024*, arXiv:2305.15334 | [ShishirPatil/gorilla](https://github.com/ShishirPatil/gorilla) @ `6ea57973c7a6` | reuse scorer |
| **Permission engine (policy)** | prospective risk classes of tool calls: what needs confirmation, what is refused | SafeToolBench: Pioneering a Prospective Benchmark to Evaluating Tool Utilization Safety in LLMs — Chen, H., et al., *EMNLP 2025 Findings*, arXiv:2509.07315 | [BITHLP/SafeToolBench](https://github.com/BITHLP/SafeToolBench) @ `ffdef6e782b0` | adapt taxonomy |
| **Permission engine (enforcement)** | runtime interception of tool calls before they execute | AgentTrust: Runtime Safety Evaluation and Interception for AI Agent Tool Use — Chen, L., et al., *arXiv 2026*, arXiv:2605.04785 | [chenglin1112/AgentTrust](https://github.com/chenglin1112/AgentTrust) @ `489d739b86af` | adapt interception point |
| **Ask-before-acting** | agent–user–tool interaction under policies; measures whether the agent asks the user when it must | τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains — Yao, S., Shinn, N., Razavi, P., Narasimhan, K., *arXiv 2024*, arXiv:2406.12045 | [sierra-research/tau-bench](https://github.com/sierra-research/tau-bench) @ `59a200c6d575` | reuse benchmark |
| **Long-running workflows** | durable execution with checkpoints and human-approval interrupts | LangGraph (framework; human-in-the-loop interrupts, durable execution) — LangChain Inc., *software*, https://langchain-ai.github.io/langgraph/ | [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) @ `07b33185eab8` | candidate runtime (evaluate vs own job queue) |
| **Evaluation world** | 750 tasks over simulated everyday apps (email, calendar, shopping, payments) with people | AppWorld: A Controllable World of Apps and People for Benchmarking Interactive Coding Agents — Trivedi, H., Khot, T., Hartmann, M., Manku, R., Dong, V., Li, E., Gupta, S., Sabharwal, A., Balasubramanian, N., *ACL 2024 (best resource paper)*, arXiv:2407.18901 | [StonyBrookNLP/appworld](https://github.com/StonyBrookNLP/appworld) @ `42b5bcf3cd33` | reuse benchmark verbatim: primary evaluation |
| **Evaluation (personal)** | personal-assistant tasks over 17 simulated real apps | MyPCBench: A Benchmark for Personally Intelligent Computer-Use Agents — Jang, L., et al., *arXiv 2026*, arXiv:2606.16748 | [ljang0/MyPCBench](https://github.com/ljang0/MyPCBench) @ `937ec4988250` | reuse benchmark |
| **Evaluation (tools)** | complex tasks through real MCP servers | MCP-Bench: Benchmarking Tool-Using LLM Agents with Complex Real-World Tasks via MCP Servers — Wang, Z., et al., *NeurIPS 2025 workshop*, arXiv:2508.20453 | [Accenture/mcp-bench](https://github.com/Accenture/mcp-bench) @ `7a8eaeae83a8` | reuse benchmark |
| **Travel workflow** | multi-constraint trip planning with tools and budgets | TravelPlanner: A Benchmark for Real-World Planning with Language Agents — Xie, J., Zhang, K., Chen, J., Zhu, T., Lou, R., Tian, Y., Xiao, Y., Su, Y., *ICML 2024*, arXiv:2402.01622 | [OSU-NLP-Group/TravelPlanner](https://github.com/OSU-NLP-Group/TravelPlanner) @ `e52c87f4ac34` | reuse benchmark for the travel workflow |
| **Baseline capability** | multi-environment agent evaluation | AgentBench: Evaluating LLMs as Agents — Liu, X., et al., *ICLR 2024*, arXiv:2308.03688 | [THUDM/AgentBench](https://github.com/THUDM/AgentBench) @ `d1e4a10db08c` | reuse for the capability baseline |

## What is original in LIFE OS

1. **The permission engine as a typed contract**: every tool call carries a risk class (read / write-reversible / write-irreversible / financial / external-communication) and a scope; irreversible and external actions require an explicit confirmation whose text is generated from the exact arguments, and every decision is written to the audit log before execution.
2. **Workflows as first-class objects**: a goal becomes a plan with steps, each step a tool call or a question to the user; steps run as durable jobs (the existing job infrastructure), survive restarts, and report their state to the app.
3. **The mobility module is real**: departure planning, route options and forecasts come from TrafficTwin's own models and simulation, not from a maps API wrapper.
4. **Honesty labels everywhere**: every fact the agent shows carries its provenance (which connector, which message, which run), exactly as the traffic evidence pages do.

## What must be real, and what that requires

- **Gmail and Google Calendar connectors**: OAuth 2.0 client credentials from a Google Cloud project, the user's consent on first use, tokens stored encrypted per user. No key, no connector; the app says so.
- **Files**: the user's uploaded documents, indexed locally (the same upload path the datasets use).
- **Tasks and reminders**: the app's own store (SQLite per user) with scheduled notification jobs.
- **The language model**: any provider behind one interface; tool schemas are generated from the connectors' OpenAPI/MCP descriptions, never hand-written per model.
- **Evaluation**: AppWorld and τ-bench runs with the agent, reported the same way the traffic experiments are (pre-registered protocol, run files, computed status). No number is typed in.

## Order of work

1. Orchestrator + permission engine + audit log on a fake in-memory tool set, tested against AppWorld's task format.
2. Memory (Generative Agents retrieval + Reflexion) with per-user storage.
3. Connectors: Calendar first (read/write, reversible), then Gmail (read; send = external, always confirmed), then files, tasks, mobility (TrafficTwin).
4. Workflows: study plan, commute plan, trip plan, inbox triage — each an explicit plan template the agent fills, not free-form prompting.
5. Web and mobile screens: Today, Plan, Mobility, Inbox, Me (the layout of the mockup).
