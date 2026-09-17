# AI Model, RAG, and Training Specification

## 1. Purpose
This document defines how the platform handles large language models, retrieval, knowledge access, training, and system-level intelligence while keeping the architecture practical, cost-aware, and locally operable.

## 2. Design Principle
The platform should not rely on a single giant monolithic model to perform all tasks. Instead, it should intelligently route tasks to:

- local models for lightweight or private workflows
- cloud models for complex reasoning or specialized capabilities
- domain-specific tools for fresh live information
- retrieval systems for document and project knowledge
- fine-tuned models only where there is clear value

## 3. Model Registry
The registry stores metadata about each available model:

```text
Model
  - provider
  - type
  - capabilities
  - context window
  - multimodal support
  - local/cloud
  - latency
  - cost
  - status
  - version
```

This allows the router to choose the best model for each job.

## 4. Model Router
The router decides by task type and constraints.

Examples:
- short chat -> small fast local model
- coding -> coding-specialized model
- vision -> vision model
- search-heavy requests -> search + reasoning flow
- creative generation -> generator model or pipeline
- astrology -> deterministic engine + LLM explanation layer

## 5. Local-First Architecture
The system should support local inference using Ollama, llama.cpp, vLLM, or equivalent frameworks.

Benefits:
- lower cost
- greater privacy
- offline capability for base tasks
- fast iteration on experiments

Constraints:
- may be limited by RAM/GPU
- local models may not match top-tier cloud quality
- complex tasks still benefit from stronger external models

## 6. Knowledge vs Memory vs Training
These are intentionally separate concepts.

### 6.1 Memory
User and project-specific state:
- preferences
- project context
- history
- prior tasks
- structured facts

### 6.2 Knowledge Base
Document or product knowledge:
- PDFs
- docs
- manuals
- notes
- research materials
- uploaded project files

### 6.3 Search / Live Data
Fresh facts from the web or external systems:
- current news
- weather
- stock prices
- company data
- current political info

### 6.4 Fine-Tuning
Controlled optimization for style or domain behavior.
- special formatting
- preferred coding patterns
- task-specific adaptation

Training should not happen as a side effect of every single chat.

## 7. RAG Architecture
The retrieval pipeline should work as follows:

```text
User question
  -> determine if fresh external info is needed
  -> retrieve relevant documents/chunks
  -> validate sources
  -> inject retrieved content into prompt as reference context
  -> ask model to answer using that context
  -> cite sources when relevant
```

## 8. Embedding Strategy
Use embeddings for:
- knowledge retrieval
- document similarity search
- project code retrieval
- conversation memory retrieval

Store them in a vector-capable database, ideally using Postgres + pgvector or an equivalent approach.

## 9. Live Information Strategy
The platform should explicitly test whether a query is time-sensitive.

Examples of time-sensitive queries:
- current weather
- today's headlines
- current government info
- product pricing
- local schedules

For these, create a retrieval workflow that checks real-time information before answering.

## 10. Prompt Security and Context Handling
Use prompt separation carefully:
- system instructions are authoritative
- user input is conversational content
- retrieved sources are trusted only as reference material
- document content is never allowed to override safety or instructions silently

This is essential to defend against prompt injection in documents and web pages.

## 11. Fine-Tuning Lifecycle
A good fine-tuning pipeline looks like this:

```text
collect data -> clean and validate -> define objective -> train -> evaluate -> benchmark -> stage -> production
```

Keep model changes controlled and versioned.

## 12. Evaluation Framework
Every model and agent should be benchmarked.

Evaluation should include:
- response correctness
- factuality
- instruction following
- safety and refusal behavior
- latency and cost
- tool use quality
- conversational coherence

## 13. Versioning
The platform should version:
- model versions
- prompts
- workflows
- agent definitions
- evaluation datasets
- training runs

## 14. Current Date and Time Handling
The platform must not rely on the model’s memory for the current date.

Use a trusted system clock or time API and pass that to the orchestrator/context builder.

## 15. Web and Tool Augmentation
The LLM should not be treated as the only source of truth.

The better pattern is:

```text
question -> intent -> tool search -> retrieval -> synthesis -> answer with evidence
```

This is especially important for up-to-date information, tool execution, and domain-specific tasks.

## 16. Training Safety Rules
- no invisible training from each chat
- no silent model drift
- no automatic use of private user data without explicit policy
- no unreviewed fine-tuning on production data
- log every dataset and model change

## 17. Example Routing Matrix
| Request Type | Preferred Path |
| --- | --- |
| general chat | local fast LLM |
| coding task | coding model + repo context + tests |
| current events | live search + reasoning model |
| image generation | image model pipeline |
| astrology | deterministic engine + LLM narrative |
| vector design | structured generation + renderer |
| browser automation | browser agent + Playwright |

## 18. Success Criteria
The model and knowledge system is considered healthy when it:
- answers current information accurately with evidence
- separates memory, retrieval, and training correctly
- allows controlled local-first operation
- supports safe model upgrades and evaluation
- keeps cost and latency understandable
- enables direct, testable improvements over time
