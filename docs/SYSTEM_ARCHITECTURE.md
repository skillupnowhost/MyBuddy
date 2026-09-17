# System Architecture Document

## 1. Overview
The platform is organized as a layered AI operating system with a central orchestrator and modular execution engines. The goal is to make the product feel like a single assistant while keeping each capability independently testable and replaceable.

## 2. High-Level Architecture

```text
                     USER
                      │
                      ▼
             ┌──────────────────┐
             │ AI Desktop UI    │
             │ Chat / Projects   │
             │ Code / Images     │
             │ Video / Agents    │
             └────────┬─────────┘
                      │
                      ▼
             ┌──────────────────┐
             │ AI Orchestrator   │
             │ Intent router     │
             │ Task planner      │
             │ Agent selector    │
             └───────┬──────────┘
                     │
      ┌──────────────┼─────────────────┐
      ▼              ▼                 ▼
┌──────────────┐ ┌───────────────┐ ┌──────────────┐
│ Model Router │ │ Agent System   │ │ Tool System   │
│ LLM/VLM      │ │ Coding        │ │ Search        │
│ Vision       │ │ Browser       │ │ APIs          │
│ Embeddings   │ │ Research      │ │ Files         │
│ Multilingual │ │ Test          │ │ Calendar      │
└──────┬───────┘ └──────┬────────┘ └──────┬───────┘
       │                 │                 │
       ▼                 ▼                 ▼
┌────────────────────────────────────────────────────┐
│ Specialized Engines                                │
│ Coding │ Image │ Video │ Vector │ Astrology │ Voice │
└────────────────────────────────────────────────────┘
```

## 3. Core Architectural Principles
1. Local-first, cloud-optional.
2. Modular providers and drivers.
3. Explicit separation of memory, RAG, tools, and training.
4. Every long job is asynchronous and observable.
5. Security boundaries are enforced before execution.
6. Validation is required before claiming task completion.

## 4. Component Layers
### 4.1 Presentation Layer
Responsible for desktop UI and client-side experience.

Features:
- chat workspace
- project dashboard
- code editor
- image and SVG preview
- video timeline or asset panel
- agent builder
- settings and permissions

### 4.2 API Layer
FastAPI-based backend exposing REST and streaming endpoints.

Key endpoints:
- /api/v1/chat
- /api/v1/projects
- /api/v1/agents
- /api/v1/images
- /api/v1/videos
- /api/v1/code
- /api/v1/tests
- /api/v1/search
- /api/v1/jobs
- /api/v1/astrology

Use WebSockets or SSE for progress updates, status streaming, and job monitoring.

### 4.3 Orchestration Layer
The central brain that decides intent and execution strategy.

Responsibilities:
- classify user requests
- determine required tools and models
- manage multi-step tasks
- trigger workflows and approvals
- gather results and summarize outputs

### 4.4 Model Abstraction Layer
Allows swapping providers without impacting application logic.

Common interfaces:
- generate()
- chat()
- stream()
- analyze()
- code()
- vision()
- embed()

Available backends:
- local Ollama-compatible servers
- cloud LLM providers
- specialized vision models
- embedding models
- fine-tuned local models

### 4.5 Tool Layer
Reusable capabilities exposed to agents.

Examples:
- web search
- calendar integration
- file access
- code execution (sandboxed)
- browser automation
- shell commands (restricted)
- arithmetic or calculation tools
- custom API connectors

### 4.6 Data Layer
Use PostgreSQL as the primary relational store.

Core tables:
- users
- projects
- conversations
- messages
- agents
- tools
- workflows
- jobs
- files
- documents
- chunks
- embeddings
- knowledge_bases
- model_registry
- test_runs
- test_results
- audit_logs

For vector search, use pgvector or a similar embedding store.

### 4.7 Storage Layer
Separate structured metadata from large binary content.

Binary objects:
- images
- videos
- audio
- generated project files
- exported assets
- uploaded document files

Use object storage or a managed file system for large file blobs.

## 5. Execution Models
### 5.1 Interactive Chat
Responds quickly and maintains conversation state.

### 5.2 Background Job
For expensive tasks such as:
- image generation
- video generation
- code builds
- browser automation
- training jobs
- large document ingestion

### 5.3 Agent Workflow
For multi-step operations with state, memory, tool calls, and approvals.

## 6. Security Architecture
The system must enforce a layered security model.

### Security controls
- authentication and role-based authorization
- encrypted API keys and secrets
- sandbox for untrusted code execution
- strict filesystem and network boundaries
- approval gates for destructive or external actions
- input validation and output sanitization
- audit trails for all high-risk operations

## 7. Provider Architecture
Each provider follows an explicit abstraction pattern.

Examples:
- LLMProvider
- EmbeddingProvider
- VectorStoreProvider
- SearchProvider
- ImageGenerationProvider
- VideoGenerationProvider
- SandboxProvider
- ModelRegistryProvider

This makes the product robust to future swaps such as cloud model changes, local model changes, or new execution backends.

## 8. Job and Workflow System
Every long-running task follows the same lifecycle.

```text
PENDING -> RUNNING -> WAITING_FOR_APPROVAL -> EXECUTING -> COMPLETED
                                                  \-> FAILED
                                                  \-> TIMEOUT
                                                  \-> CANCELLED
```

Each job stores:
- job_id
- status
- progress
- logs
- artifacts
- timestamps
- error details

## 9. Model Routing Strategy
The router should choose based on task characteristics.

Example mappings:
- simple factual queries -> local fast model
- coding -> coding-specialized model
- vision -> vision model
- translation -> multilingual model
- current events -> search + reasoning model
- image generation -> dedicated image pipeline
- video -> multi-stage generation pipeline

## 10. Memory and Knowledge Architecture
### Memory
Short and long-term user/project-specific context.

### Knowledge Base
Documents, manuals, and uploaded materials with embeddings and retrieval.

### Search
Live retrieval of current information from web or APIs.

### Training
Controlled fine-tuning or model optimization via explicit dataset and validation process.

## 11. Testing Architecture
The system should maintain a layered validation pipeline.

```text
code -> static analysis -> unit tests -> api tests -> integration tests -> ui tests -> e2e tests -> security checks -> reports
```

## 12. Observability and Evaluation
The system should emit structured logs and metrics for:
- request latency
- model usage
- token consumption
- tool invocations
- test runs
- agent decisions
- resource usage
- error rates

This data feeds evaluation and continuous improvement.

## 13. Recommended Deployment Layout
- Frontend app
- FastAPI backend
- PostgreSQL
- vector store / embeddings service
- Ollama or local inference server
- optional cloud API adapters
- job workers
- object storage
- sandbox containers or restricted runtime

## 14. Product Stability Principles
- Do not claim success without validation.
- Never silently hide execution failures.
- Prefer deterministic and inspectable operations over opaque magical behavior.
- Keep major capabilities module-based and independent.
- Treat the orchestrator as a planner, not a single magical black box.

## 15. Summary
The architecture is a coordinated AI operating system: a single desktop experience, a central orchestrator, multiple specialized modules, layered security, and a strong validation culture. This design scales from local self-hosted use to more advanced multi-agent systems without collapsing into a single giant model.
