# Product Requirements Document (PRD)

## 1. Product Summary
MyBuddy is a self-hosted, desktop-first multimodal AI platform that behaves like a single intelligent assistant while internally orchestrating specialized models, tools, and agents. The system combines chat, research, coding, application generation, browser automation, creative generation, astrology, voice interaction, and automation workflows into one product experience.

The design principle is: do not build one giant model that does everything. Instead, build one orchestrated platform with a central brain, specialized execution modules, and clearly separated memory, knowledge, tooling, and training pipelines.

## 2. Product Vision
The platform should feel like:

> “Tell me what you want. I’ll determine the best model, workflow, tool, and execution path.”

The user should not need to manually select a model or tool for every task. The orchestrator decides based on the request, constraints, and project context.

## 3. Core User Scenarios
### 3.1 General AI Chat
- Ask general questions in natural language.
- Receive conversational responses with good reasoning.
- Support multiple supported languages.
- Keep recent project and user context available.

### 3.2 Research and Current Information
- Answer questions that require fresh information.
- Retrieve sources from live web/search APIs.
- Attribute sources and preserve dates.
- Cite evidence rather than rely on stale model memory.

### 3.3 Coding and Engineering
- Generate code and project scaffolds.
- Explain existing code.
- Debug failing code.
- Run tests and validate behavior.
- Fix issues and re-run validation.
- Manage Git and repository workflows.

### 3.4 Full Application Generation
- Take a business or product idea.
- Build a project plan and architecture.
- Generate frontend, backend, database, tests, and docs.
- Run validation checks and report results honestly.
- Produce deployable project artifacts.

### 3.5 Browser Automation and Testing
- Generate Playwright or browser automation scripts.
- Execute them in a controlled environment.
- Capture failures, screenshots, and traces.
- Feed failures back into the coding/debugging loop.

### 3.6 Creative Workflows
- Generate and edit images.
- Generate SVG and vector art.
- Animate scenes and UI elements.
- Create short video pipelines from script to export.

### 3.7 Astrology and Knowledge Tools
- Offer horoscope, birth chart, planetary calculations, compatibility, and name analysis.
- Use deterministic calculations where appropriate.
- Use LLM interpretation only for explanatory output.

### 3.8 Agent and Automation Builder
- Create custom agents from natural language.
- Define workflows with triggers, permissions, memory, tools, and approval steps.
- Allow users to review and approve high-risk actions.

## 4. Functional Requirements
### 4.1 Orchestration Layer
- Accept any user request through a single interface.
- Classify request intent.
- Select the appropriate model, agent, and tools.
- Route long-running tasks into jobs with progress updates.

### 4.2 Model Router
- Support local and cloud models through one abstraction layer.
- Route by task type and resource constraints.
- Keep model selection transparent to product logic.

### 4.3 Knowledge and Memory
- Distinguish memory, RAG, search, and fine-tuning.
- Use per-user memory for preferences and project context.
- Store document knowledge in searchable knowledge bases.
- Use fresh web data via live retrieval for time-sensitive questions.
- Use controlled training only for deliberate optimization.

### 4.4 Coding Agent
- Read project files and code structure.
- Modify code and run validation.
- Level of privilege should be explicit and secure.
- Use sandboxed or restricted execution for untrusted operations.

### 4.5 Automation and Agents
- Allow task execution and workflow creation.
- Require approval for sensitive or destructive actions.
- Maintain logs for every action and result.

### 4.6 Creative Tools
- Generate and edit images.
- Generate editable SVG output.
- Support animation and video pipelines.
- Provide progress reporting with real pipeline stages.

### 4.7 Multilingual Support
- Detect input language.
- Reason in the correct semantic context.
- Respond in requested output language.
- Avoid blindly translating before understanding.

## 5. Non-Functional Requirements
### 5.1 Security
- Secure authentication and authorization.
- Encrypt secrets and sensitive configuration.
- Restrict arbitrary terminal execution.
- Audit logs for critical actions.
- Sandbox agent actions where feasible.

### 5.2 Performance
- Simple chats should feel near-instant.
- Long tasks should stream progress and run in the background.
- Use asynchronous jobs for heavy operations.

### 5.3 Reliability
- Every operation should be observable.
- Failed tests and failed jobs must be surfaced honestly.
- Recovery and retry logic should exist for transient errors.

### 5.4 Extensibility
- Abstractions should allow swapping providers and engines.
- Agents and tools should be modular.
- Model registry should support future additions without breaking core logic.

## 6. UX Requirements
- Unified prompt input supporting text, files, images, voice, URL, and code.
- Multi-area desktop workspace with navigation and project views.
- Real-time progress display for jobs.
- Results in text, code, image, SVG, video, charts, or downloadable files.

## 7. Scope
### In Scope
- Chat and orchestration
- Local LLM support
- RAG and knowledge base
- Memory
- Coding agent
- Browser automation
- Creative generation
- Voice and localization
- Agent builder
- Background job system
- Postgres-based platform foundation

### Out of Scope for Initial Release
- Full autonomous self-reproduction of arbitrary software with no approval
- Unrestricted internet execution for all agents
- Massive multi-tenant cloud scaling
- Unsafe unrestricted system shell access to all users
- Fully autonomous deployment to production without human review

## 8. Phased Delivery Plan
### Phase 1 — Foundation
- Desktop UI
- FastAPI backend
- Postgres
- local LLM integration
- project system and chat

### Phase 2 — Knowledge
- RAG
- embeddings
- document ingestion
- search and citations

### Phase 3 — Memory and tools
- memory
- tool calling
- user preferences and project context

### Phase 4 — Coding
- code chat
- code project RAG
- sandboxed execution
- Git and test validation

### Phase 5 — Browser automation and testing
- Playwright agent
- UI test generation
- failure analysis loops

### Phase 6 — Creative and vector tools
- SVG generation and editing
- animation and motion composition
- video generation pipeline

### Phase 7 — Astrology and multilingual support
- deterministic astrology engine
- language-aware response handling

### Phase 8 — Agent builder and automation
- custom agents
- workflow builder
- approval gates

## 9. Acceptance Criteria
The platform is considered successful when it can:

1. Accept a user request without needing manual model selection.
2. Determine correct intent and route to the right tool or agent.
3. Perform simple chat, research, coding, and creative tasks in a coherent flow.
4. Distinguish memory from knowledge from training.
5. Run validation for code and tests before reporting success.
6. Maintain traceable logs and progress reports for long-running tasks.
7. Require approval for high-risk actions.
8. Support a local-first architecture that works without mandatory cloud APIs.
9. Produce real outputs that can be inspected, downloaded, or validated.
10. Maintain user trust through honest status reporting and evidence-based results.
