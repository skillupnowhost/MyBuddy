# Master Build Prompt

You are building a complete AI platform called MyBuddy, a self-hosted desktop-first multimodal AI system. Build the product as a real software system, not as a single giant monolithic model.

## Product Goal
Create one AI platform that feels like a single intelligent assistant with multiple specialized capabilities:
- chat
- research
- coding
- project generation
- testing and browser automation
- image generation and editing
- SVG/vector generation and editing
- animation and motion workflows
- video generation and editing
- astrology and deterministic calculations
- multilingual responses
- custom agent creation
- workflow automation
- project management and library organization

The user should experience one AI interface, while the backend routes work to the correct model, tool, agent, or workflow.

## Core Design Principle
Do NOT build one giant all-purpose model. Build:
- a central orchestrator
- a model router
- agent system
- tool system
- specialized engines
- retrieval and memory systems
- validation and testing loop

The intelligence comes from orchestration, tools, retrieval, memory, execution, and validation, not just a single base LLM.

## Product Architecture
Use this structure:

```text
User
  -> AI Desktop Interface
    -> AI Orchestrator
      -> Model Router
      -> Agent System
      -> Tool System
      -> Specialized Engines
          -> Coding
          -> Image
          -> Video
          -> Vector/SVG
          -> Astrology
          -> Voice
```

## Required Functional Modules
1. Chat system with multiple modes.
2. Research mode with source citations and current-data retrieval.
3. Coding agent with repository context and validation.
4. Full project builder that writes complete working applications.
5. Browser automation and Playwright testing.
6. Image generation and editing.
7. Vector and SVG generation/editing.
8. Animation and motion workflows.
9. Video generation and editing pipeline.
10. Astrology engine with deterministic calculations + LLM interpretation.
11. multilingual support.
12. custom agent builder.
13. automation/workflow builder.
14. background job system with progress tracking.
15. library/project workspace architecture.

## Required Technical Architecture
- Frontend: modern desktop-first application UI.
- Backend: FastAPI service layer.
- Database: PostgreSQL as primary system of record.
- Vector storage: support embeddings via pgvector or equivalent.
- Local inference: support Ollama or similar local LLM stack.
- Model abstraction layer for local/cloud models.
- Job queue for async tasks.
- REST + streaming endpoints for real-time progress.
- Storage separation for metadata vs large files.
- Security: auth, authorization, secrets, sandboxing, logs, approvals.

## Memory and Knowledge Separation
The system must explicitly distinguish:
- memory
- knowledge base
- live search/current info
- training/fine-tuning

Do not treat them as the same thing. Use each for its correct purpose.

## Research and Fresh Data Requirement
If the query is time-sensitive, the system must detect that and fetch fresh evidence from reliable sources before answering. Preserve source attribution and dates. Do not answer based only on stale model memory.

## Coding Requirements
The coding system must support:
- repo-aware coding
- debugging
- refactoring
- tests
- browser automation
- Playwright and UI testing
- secure execution sandbox
- Git and validation loops

The system must never claim success without running validation and checking test or execution results.

## Testing and Validation Requirements
Every major task must have a validation layer.

```text
Code -> static analysis -> unit tests -> API tests -> integration -> UI -> E2E -> report
```

When tests fail, the system must analyze the failure, edit the code, and re-run the relevant validation.

## Security Requirements
- authenticated and authorized access
- encrypted secrets
- restricted shell/terminal execution
- sandboxing for untrusted code
- approval gates for destructive actions
- audit logs for important events

## Agent Requirements
Custom agents must have:
- identity
- purpose
- instruction set
- tools
- permissions
- memory
- triggers
- workflow steps
- approval rules
- monitoring and logging

Do not allow unrestricted high-risk operations without approval.

## Creative Requirements
Support image generation and editing, vector generation, animation, and video workflows. The system should provide real progress reporting tied to actual pipeline stages, not fake percentages.

## Astrology Requirements
Use a deterministic calculation engine for astrological logic and a separate LLM layer for interpretation. Do not let the LLM pseudo-calculate everything.

## Multilingual Requirements
Support multilingual users without blindly translating before understanding. Detect the input language, reason semantically, and respond in the requested output language.

## User Experience Requirements
- one unified prompt input for text, files, images, URLs, and code
- desktop-like workspace layout
- progress streaming for long-running jobs
- real artifacts as output: code, docs, images, SVG, video, reports, downloadable files

## Production Constraints
- local-first and optional cloud
- modular provider architecture
- explicit versioning and evaluation
- observability and logging
- asynchronous processing for expensive tasks
- honest status reporting and failure handling

## Deliverable Expectations
Build the platform in a way that can realistically run in this repository and align with the MyBuddy project structure.

You must:
1. Keep the architecture modular.
2. Prioritize a working foundation before adding advanced capabilities.
3. Build the software using real code and real validation.
4. Avoid fake or non-functional claims.
5. Prefer deterministic, inspectable behavior over hidden magic.
6. Implement the architecture in phases rather than trying to do everything at once.

## Final Instruction
Now produce the actual implementation plan, architecture files, API contracts, service layout, and code structure needed to build MyBuddy as a working AI platform. Keep the implementation grounded in reality, local-first deployment, and honest capability limits.
