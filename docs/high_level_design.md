# TinyTroupe — High-Level Design Document

> **Scope.** This document captures the main architectural decisions of the TinyTroupe codebase, with emphasis on the `tinytroupe/` package. It is intended for contributors, researchers, and engineers who need to understand, use, or extend the framework.

---

## 1. Overview & Purpose

**TinyTroupe** is a Python framework for building **LLM-powered multi-agent simulations**. It lets users define synthetic personas ("TinyPersons"), place them in simulated environments ("TinyWorlds"), and have them perceive stimuli, reason about them, and act — producing realistic conversational, behavioral, or decision-making traces.

### Primary use cases

| Use Case | Example Notebook(s) |
|----------|---------------------|
| **Market research** with synthetic customer panels | `Bottled Gazpacho Market Research`, `AI-enabled Children Story Telling Market Research` |
| **Product brainstorming** and focus groups | `Product Brainstorming` |
| **Customer interviews** | `Interview with Customer` |
| **Synthetic data generation** | `Synthetic Data Generation 1/2` |
| **Advertisement & creative testing** | `Advertisement for TV`, `Online Advertisement for Travel` |
| **Political / opinion simulation** | `Political Compass` |
| **Long-form narrative generation** | `Story telling (long narratives)` |
| **Multimodal (vision) tasks** | `Vision for Product, Diagnosis and Appreciation Feedback` |
| **Controlled experimentation** | `publications/paper_artifacts_*` |
| **Software architecture evaluation** | `atamsim` package (ATAM simulations) |

### Design philosophy

1. **LLM-first cognition** — agents reason using a cognitive architecture built on top of LLM calls, not hand-written rules.
2. **Persona-driven** — every agent is defined by a rich persona specification that governs its behavior.
3. **Reproducibility by construction** — the transactional caching system makes simulations deterministic and replayable.
4. **Extensibility** — every major subsystem (LLM client, memory, tools, environments, faculties) is pluggable.
5. **Safety-aware** — real-world side effects, content filters, and ownership checks are first-class concerns.

### Domain-specific extensions

Beyond the general-purpose framework, TinyTroupe supports **domain-specific extension packages**. The `atamsim` package (see §11) implements the Architecture Tradeoff Analysis Method (ATAM) for software architecture evaluation, demonstrating how the core abstractions — `TinyPerson`, `TinyWorld`, `TinyPersonFactory` — can be composed into a structured, multi-phase simulation workflow.

---

## 2. Architecture at a Glance

```
┌──────────────────────────────────────────────────────────────────────┐
│                        User Code / Notebooks                          │
│                  (examples/, publications/)                           │
├──────────────────────────────────────────────────────────────────────┤
│  Simulation Control Layer (control.py)                                │
│  ┌────────────────┐   ┌──────────────────┐   ┌────────────────────┐ │
│  │  Simulation    │   │  Transaction     │   │  @transactional    │ │
│  │  (trace/cache) │   │  (event hashing) │   │  decorator         │ │
│  └────────────────┘   └──────────────────┘   └────────────────────┘ │
├──────────────────────────────────────────────────────────────────────┤
│  Environment Layer (environment/)                                     │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  TinyWorld  ──┬──>  TinyWorld with target agent                  ││
│  │               ├──>  broadcast, stimulus routing, step() loop     ││
│  │               └──>  parallel / sequential agent execution        ││
│  └─────────────────────────────────────────────────────────────────┘│
├──────────────────────────────────────────────────────────────────────┤
│  Agent Cognition Layer (agent/)                                       │
│  ┌───────────┐  ┌───────────┐  ┌──────────────┐  ┌───────────────┐ │
│  │ TinyPerson│  │  Memory   │  │ Action       │  │  Mental       │ │
│  │ (persona) │  │  (episodic│  │ Generator    │  │  Faculties    │ │
│  │           │  │  +sem.)   │  │ (quality)    │  │  (perceive,   │ │
│  │           │  │           │  │              │  │   reason, etc)│ │
│  └───────────┘  └───────────┘  └──────────────┘  └───────────────┘ │
├──────────────────────────────────────────────────────────────────────┤
│  Supporting Subsystems                                                │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐ │
│  │ Factory │ │  Tools   │ │Enrichment│ │Validation│ │Extraction │ │
│  │(agents) │ │(actions) │ │          │ │(proposi- │ │(results)  │ │
│  └─────────┘ └──────────┘ └──────────┘ │  tions)  │ └───────────┘ │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────┐ ┌────────────────┐│
│  │  Profiling   │ │Steering      │ │   UI     │ │ Experimentation││
│  │  (analysis)  │ │(intervention)│ │(display) │ │  (propositions)││
│  └──────────────┘ └──────────────┘ └──────────┘ └────────────────┘│
├──────────────────────────────────────────────────────────────────────┤
│  Foundation / Cross-cutting                                           │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────┐ ┌────────────┐  │
│  │ ConfigManager│  │  LLM Clients  │  │  Utils   │ │ Logging    │  │
│  │  + config.ini│  │  (openai/     │  │ (registry│ │            │  │
│  │              │  │   azure/ollama)│  │  /hash)  │ │            │  │
│  └──────────────┘  └───────────────┘  └──────────┘ └────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### Module map

| Directory | Responsibility |
|-----------|----------------|
| `tinytroupe/` (root) | Configuration, simulation control, profiling |
| `tinytroupe/agent/` | Agent definition, memory, cognitive faculties, action generation |
| `tinytroupe/environment/` | World model, stimulus routing, turn management |
| `tinytroupe/factory/` | Agent and population generation |
| `tinytroupe/clients/` | LLM backend abstraction (OpenAI, Azure, Ollama, LlamaIndex) |
| `tinytroupe/tools/` | Agent-callable tools (word processor, calendar) |
| `tinytroupe/enrichment/` | Post-processing enrichment of results |
| `tinytroupe/extraction/` | Structured extraction from simulation outputs |
| `tinytroupe/validation/` | Proposition-based validation of agents/simulations |
| `tinytroupe/experimentation/` | Quantitative experimental primitives |
| `tinytroupe/steering/` | Runtime intervention and behavior steering |
| `tinytroupe/ui/` | Rich console / Jupyter display |
| `tinytroupe/utils/` | Serialization, hashing, prompts, concurrency |

---

## 3. Core Design Decisions

### 3.1 LLM-Centric Cognitive Architecture

**Decision:** Agents do not follow scripted rules. Instead, their cognition is a sequence of LLM calls structured around a **dual-memory model**.

**Memory system** (`agent/memory.py`):

- **Episodic memory** — a time-ordered log of all stimuli received and actions produced. This is the "raw experience" of the agent.
- **Semantic memory** — abstracted knowledge derived from episodic memory through **consolidation**. Uses LlamaIndex embeddings for similarity-based retrieval.

**Memory consolidation** (configurable via `[Cognition]`):

```
Episodic Memory  ──consolidate──>  Semantic Memory
(verbatim)                        (semantic chunks)
```

- `MIN_EPISODE_LENGTH` / `MAX_EPISODE_LENGTH` — control when an episode is chunked.
- `ENABLE_MEMORY_CONSOLIDATION` — toggles the whole mechanism.
- `ENABLE_CONTINUOUS_CONTEXTUAL_SEMANTIC_MEMORY_RETRIEVAL` — enables ongoing retrieval of relevant semantic memories.

**Mental faculties** (`agent/mental_faculty.py`): reusable cognitive operations (perceive, recall, reason, plan) that an agent can invoke. These are composable and LLM-backed.

### 3.2 Transactional Caching for Reproducibility

**Decision:** Every state-changing operation on agents/worlds is wrapped in a `@transactional` decorator that records an **execution trace**. This enables:

1. **Deterministic replay** — re-running a simulation skips cached LLM calls.
2. **Incremental development** — change a prompt, re-run, and only the divergent path is recomputed.
3. **Cost control** — cached API calls are skipped entirely.

**How it works** (`control.py`):

```python
@transactional
def some_agent_method(self, ...):
    ...
```

- On first execution, the function call arguments are **hashed** (`_function_call_hash`), the function runs, and the resulting simulation state is serialized into the `cached_trace`.
- On subsequent runs, the hash is compared; if it matches, the state is **decoded from cache** and the function body is skipped.
- A **parallel transactions** mechanism handles concurrent agent execution within a single step.

**Key classes:**

| Class | Role |
|-------|------|
| `Simulation` | Holds agents, environments, factories, the cached/execution traces |
| `Transaction` | Orchestrates a single transactional execution with cache lookup |
| `@transactional` | Decorator that wraps methods of `TinyPerson`/`TinyWorld`/`TinyFactory` |

**Output encoding:** Function returns are encoded using type tags (`TinyPersonRef`, `TinyWorldRef`, `JSON`, `List`) so object identity is preserved across cache boundaries.

### 3.3 Configuration-Driven Design

**Decision:** All runtime parameters flow through a single `ConfigManager` that merges `config.ini` defaults with runtime overrides.

**Layers:**

```
config.ini  ──>  ConfigManager._initialize_from_config()  ──>  self._config dict
                                                            │
                            runtime overrides ──────────────┘
                            (config_manager.update("model", "gpt-5"))
```

**Key features:**

- **`get(key, override)`** — central lookup helper used in method signatures.
- **`@config_defaults(model="model")`** — decorator that injects current config values for `None` parameters.
- **`get_with_fallback(key, fallback)`** — e.g., `vision_model` falls back to `model`.
- **Hot-reloadable log levels** — updating `loglevel` immediately reconfigures handlers.
- **Concurrency limit parsing** — `MAX_CONCURRENT_MODEL_CALLS` accepts `NONE`/`OFF`/integers.

**Config sections:** `[OpenAI]`, `[Simulation]`, `[Cognition]`, `[ActionGenerator]`, `[Logging]`.

### 3.4 Persona-Driven Agent Model

**Decision:** An agent's behavior is governed by a **persona specification** — a structured description covering demographics, occupation, personality traits, interests, skills, beliefs, goals, routines, relationships, health, and communication style.

**`TinyPerson`** (`agent/tiny_person.py`) is the central agent class:

- Holds the persona definition and provides `get("path.to.attribute")` access (dot notation).
- Maintains episodic and semantic memory.
- Exposes cognitive operations: `see()`, `listen()`, `think()`, `act()`, `listen_and_act()`.
- Supports serialization via `encode_complete_state()` / `decode_complete_state()`.
- Tracks a `_image_registry` for multimodal (vision) stimuli.

**Persona customization with fragments:** The `examples/fragments/` directory contains reusable persona fragments (e.g., `picky_customer`, `travel_enthusiast`, political leanings) that can be **merged** into a base persona — a composable mixin pattern.

### 3.5 Quality-Controlled Action Generation

**Decision:** Agent actions go through an optional **multi-stage quality pipeline** before being committed.

**`ActionGenerator`** (`agent/action_generator.py`):

```
Tentative Action
      │
      ▼
┌─────────────────────────────────┐
│ Quality Checks (Propositions)   │
│  • Persona adherence            │
│  • Self-consistency             │
│  • Fluency                      │
│  • Suitability                  │
│  • Similarity (Jaccard)         │
└──────────────┬──────────────────┘
               │
      ┌────────┴────────┐
      ▼                 ▼
   PASS            FAIL
      │                 │
      ▼                 ├──> Regenerate (LLM re-call with feedback)
   Return            │      (up to MAX_ATTEMPTS)
                     │
                     ├──> Direct Correction (rule-based rephrasing)
                     │
                     └──> Best-effort return (if continue_on_failure)
```

- Each check uses a **Proposition** (`validation/propositions.py`) scored 0–9 by the LLM.
- `QUALITY_THRESHOLD` determines the pass/fail cutoff.
- **Negative feedback** is fed back to the agent for the next attempt.
- **Multi-action output** — the LLM can emit a full sequence of actions for a turn, terminated by `DONE`.

### 3.6 Multi-Backend LLM Abstraction

**Decision:** The framework abstracts LLM access behind a `client()` interface, supporting multiple backends.

**Backends** (`clients/`):

| Backend | Notes |
|---------|-------|
| **OpenAI** (default) | `API_TYPE=openai`, `MODEL=gpt-5-mini` |
| **Azure OpenAI** | `API_TYPE=azure`, separate API version config |
| **Ollama** | Local models via `examples/ollama/` |
| **LlamaIndex embeddings** | Used for semantic memory (OpenAI or Azure embedding models) |

**Cross-cutting features:**

- **API call caching** (`CACHE_API_CALLS`, `CACHE_FILE_NAME`) — file-based JSON cache.
- **Concurrency limiting** — `MAX_CONCURRENT_MODEL_CALLS` throttles parallel LLM calls.
- **Retry with exponential backoff** — `MAX_ATTEMPTS`, `WAITING_TIME`, `EXPONENTIAL_BACKOFF_FACTOR`.
- **Model specialization** — separate config for `MODEL`, `REASONING_MODEL`, `VISION_MODEL`, `EMBEDDING_MODEL`.
- **Structured output** — Pydantic response models (`CognitiveActionModel`, `CognitiveActionsModel`) enforce JSON schema compliance.

### 3.7 Parallel Execution Model

**Decision:** Agent generation and per-step actions can run in parallel.

Controlled by `[Simulation]` flags:

| Flag | Effect |
|------|--------|
| `PARALLEL_AGENT_GENERATION` | Factory generates multiple agents concurrently |
| `PARALLEL_AGENT_ACTIONS` | Agents within a world step act concurrently |
| `MAX_CONCURRENT_MODEL_CALLS` | Semphore cap on simultaneous LLM calls |

The `control.py` parallel transaction mechanism (`begin_parallel_transactions`/`end_parallel_transactions`) ensures cache consistency under concurrency using a `concurrent_execution_lock`.

### 3.8 Environment Model

**Decision:** Agents operate inside a `TinyWorld` that manages turn-taking, stimulus broadcast, and display.

**`TinyWorld`** (`environment/tiny_world.py`):

- `step()` — advances the simulation by one turn; each agent perceives and acts.
- `broadcast()` — sends a stimulus to all agents.
- Communication display (Rich/Jupyter) is configurable.
- `TinyWorld` extends a base `TinyEnvironment` and integrates with the transactional system.
- Agents can be grouped or addressed individually (`@target_agent`).

---

## 4. Data Flow

### 4.1 Stimulus-to-Action Flow

```
                    ┌──────────────────────────────────────┐
                    │            TinyWorld.step()          │
                    └────────────────┬─────────────────────┘
                                     │
                    ┌────────────────▼─────────────────────┐
                    │  Stimulus (see/listen/read/think)    │
                    │  ──> appended to Episodic Memory     │
                    └────────────────┬─────────────────────┘
                                     │
                    ┌────────────────▼─────────────────────┐
                    │  [Optional] Consolidation            │
                    │  Episodic ──> Semantic Memory        │
                    │  (embedding + chunking)              │
                    └────────────────┬─────────────────────┘
                                     │
                    ┌────────────────▼─────────────────────┐
                    │  ActionGenerator.generate_next_action│
                    │  ── builds context from memory ──    │
                    │  ── LLM call (with schema) ────────  │
                    │  ── quality checks ───────────────   │
                    │  ── regenerations (if needed) ───    │
                    └────────────────┬─────────────────────┘
                                     │
                    ┌────────────────▼─────────────────────┐
                    │  Action execution                    │
                    │  • TALK → broadcast to others        │
                    │  • DONE → end turn                   │
                    │  • TOOL → invoke TinyTool            │
                    │  • Other cognitive actions           │
                    └──────────────────────────────────────┘
```

### 4.2 Transactional Cache Flow

```
begin(cache_path="sim.cache.json")
    │
    ├──> load cached_trace from file (if exists)
    │
    └──> ... agent acts ...
            │
            @transactional wraps the method
            │
            ├── hash(function_name, args, kwargs)
            │
            ├── is this event cached AND prev node matches?
            │       ├── YES → decode state from cache, return cached output
            │       │         (cache_hits++)
            │       │
            │       └── NO  → execute function for real
            │                  ├── encode new state
            │                  ├── append to execution_trace
            │                  ├── append to cached_trace
            │                  └── cache_misses++
            │
end()
    └──> checkpoint() → save cached_trace to file
```

---

## 5. Module Deep-Dives

### 5.1 Agent Subsystem (`agent/`)

| File | Responsibility |
|------|----------------|
| `tiny_person.py` | Core `TinyPerson` class — persona, memory, cognitive operations |
| `memory.py` | Episodic + semantic memory, consolidation |
| `mental_faculty.py` | Reusable cognitive faculties (perceive, reason, etc.) |
| `action_generator.py` | LLM-driven action generation with quality control |
| `factories` | Persona-related factory helpers |

**Key pattern — `@transactional`:** Most `TinyPerson` methods that change state are decorated, making the entire agent lifecycle replayable.

### 5.2 Factory Subsystem (`factory/`)

| File | Responsibility |
|------|----------------|
| `tiny_factory.py` | Base `TinyFactory` (serializable, simulation-aware) |
| `tiny_person_factory.py` | LLM-driven persona generation from context descriptions |

**Usage:** `TinyPersonFactory("context description").generate_persons(n)` produces a panel of agents with uniqueness enforcement (no duplicate names/personas).

### 5.3 Environment Subsystem (`environment/`)

| File | Responsibility |
|------|----------------|
| `tiny_world.py` | `TinyWorld` — main simulation environment |
| Base classes | Stimulus routing, display, step loop |

### 5.4 Tools Subsystem (`tools/`)

| File | Responsibility |
|------|----------------|
| `tiny_tool.py` | Base `TinyTool` class — ownership, side-effect warnings, retry |
| `tiny_word_processor.py` | Word processor tool (document creation) |
| `tiny_calendar.py` | Calendar/scheduling tool |

**Design:** Tools define `actions_definitions_prompt()` and `actions_constraints_prompt()` that inject available actions into the agent's context. When an agent emits a `TOOL` action, `process_action()` dispatches to the tool. Tools support `ArtifactExporter` and `Enricher` for output handling.

### 5.5 Validation Subsystem (`validation/`)

Uses **Propositions** — LLM-scored claims (0–9 scale) about agent behavior:

- `hard_action_persona_adherence` — does the action match the persona?
- `action_self_consistency` — is the action consistent with prior actions?
- `action_fluency` — is the language natural and non-repetitive?
- `action_suitability` — is the action appropriate to the situation?

Used both inside `ActionGenerator` (runtime quality checks) and standalone for post-hoc validation.

### 5.6 Experimentation Subsystem (`experimentation/`)

Provides `Proposition`-based quantitative evaluation of simulations — scoring agents against claims to produce metrics for research papers (see `publications/paper_artifacts_*`).

### 5.7 Extraction Subsystem (`extraction/`)

Structured data extraction from simulation transcripts — converts free-form agent interactions into tabular/JSON results (e.g., survey responses, idea rankings). Includes a `Normalizer` for clustering semantic categories.

### 5.8 Enrichment Subsystem (`enrichment/`)

Post-processing hooks that augment tool outputs or extraction results (e.g., adding metadata, computing derived fields).

### 5.9 Profiling Subsystem (`profiling.py`)

`Profiler` analyzes agent populations:

- **Demographics** — age distribution, occupation/geographic diversity (Shannon index).
- **Persona composition** — facets (interests, skills, beliefs, goals, likes/dislikes, routines, roles, communication style, health, personality traits) with LLM-driven normalization/clustering.
- **Correlations** — numerical attribute correlation matrices.
- **Visualizations** — pie charts, bar charts, heatmaps (matplotlib/seaborn).
- **Comparisons** — cross-population comparison.
- Stores raw DataFrames in `self.plot_data` for programmatic reuse.

### 5.10 Steering Subsystem (`steering/`)

Runtime interventions — modify agent behavior mid-simulation (e.g., injecting rules, nudging opinions).

### 5.11 Clients Subsystem (`clients/`)

LLM backend abstraction with caching, concurrency control, retry logic, and structured output enforcement.

### 5.12 UI Subsystem (`ui/`)

Rich-based console and Jupyter HTML rendering for real-time simulation display.

---

## 6. Key Design Patterns

| Pattern | Where Used | Purpose |
|---------|------------|---------|
| **Decorator (transactional)** | `control.py` → agent/world methods | Caching, replay, cache invalidation |
| **Decorator (config_defaults)** | `__init__.py` | Inject config values into `None` params |
| **Decorator (repeat_on_error)** | `utils/` → LLM calls, tool execution | Retry with cache invalidation |
| **Decorator (post_init)** | agent setup | Subclass initialization hooks |
| **Factory** | `factory/` | Agent/population generation |
| **Strategy** | `clients/`, quality checks | Pluggable backends, propositions |
| **Registry / Serialization** | `utils/JsonSerializableRegistry` | State encoding/decoding for caching |
| **Template Method** | `TinyTool._process_action` | Tool dispatch |
| **Observer** | Environment stimulus broadcast | Agent notification |
| **Mixin / Fragment** | `examples/fragments/` | Composable persona customization |

---

## 7. Usage Patterns

### 7.1 Creating Agents

**Manually:**

```python
from tinytroupe.agent import TinyPerson

agent = TinyPerson(name="Lisa")
agent.define("age", 28)
agent.define("occupation", {"title": "Designer", "description": "..."})
agent.define("personality_traits", ["creative", "detail-oriented"])
agent.define("interests", ["art", "technology"])
```

**From JSON:**

```python
agent = TinyPerson.from_json_file("examples/agents/Lisa.agent.json")
```

**Via Factory:**

```python
from tinytroupe.factory import TinyPersonFactory

factory = TinyPersonFactory(
    "A panel of Brazilian software engineers, ages 25-40, varied backgrounds."
)
agents = factory.generate_people(5)  # parallel generation
```

### 7.2 Running a Simulation

```python
import tinytroupe.control as control

# Start simulation with caching for reproducibility
control.begin("my_sim.cache.json")

world = TinyWorld("Focus Group", agents=[agent1, agent2, agent3])
world.broadcast("Welcome to the focus group. Please discuss the product.")

# Run 5 turns
world.run(5)

# Save state
control.checkpoint()
control.end()
```

**Re-running** with the same cache file will replay deterministically without LLM calls (unless the trajectory diverges).

### 7.3 Market Research Workflow

```python
# 1. Generate a customer panel
factory = TinyPersonFactory("Target market: parents of young children interested in AI toys")
customers = factory.generate_people(10)

# 2. Profile the population
from tinytroupe.profiling import Profiler
profiler = Profiler()
profiler.profile(customers, plot=True)

# 3. Simulate product evaluation
world = TinyWorld("Product Eval", agents=customers)
world.broadcast(product_description)
world.run(3)

# 4. Extract structured results
from tinytroupe.extraction import ResultsExtractor
extractor = ResultsExtractor()
results = extractor.extract_results_from_world(world, 
    extraction_objective="Extract purchase intent and feedback")
```

### 7.4 Using Tools

```python
from tinytroupe.tools import TinyWordProcessor

wp = TinyWordProcessor(owner=agent)
agent.add_tool(wp)

# The agent can now emit WRITE_DOCUMENT actions during simulation
world.run(5)  # agent may autonomously use the word processor
```

### 7.5 Validation

```python
from tinytroupe.validation import TinyPersonValidator

validator = TinyPersonValidator()
results = validator.validate_person(
    agent,
    expectations="The agent should behave like a picky customer",
    recent_actions=agent.episodic_memory.retrieve_last(k=20)
)
```

---

## 8. Extension Points

### 8.1 Adding a Custom LLM Backend

Implement the client interface in `clients/`:

```python
class MyCustomClient:
    def send_message(self, messages, model=None, response_format=None, **kwargs):
        # Return {"role": "assistant", "content": "..."}
        ...
```

Register it via `API_TYPE` in `config.ini` or wire it through the `client()` factory function.

### 8.2 Adding a Custom Tool

Subclass `TinyTool`:

```python
from tinytroupe.tools import TinyTool

class DatabaseQueryTool(TinyTool):
    def __init__(self, **kwargs):
        super().__init__(name="DBQuery", 
                         description="Query a simulated database", **kwargs)
    
    def actions_definitions_prompt(self):
        return "You can use QUERY_DATABASE to search for information."
    
    def actions_constraints_prompt(self):
        return "QUERY_DATABASE requires a 'query' field."
    
    def _process_action(self, agent, action):
        if action["type"] == "QUERY_DATABASE":
            results = self._execute_query(action["query"])
            agent.read(f"Database results: {results}")
            return True
        return False
```

Then `agent.add_tool(DatabaseQueryTool(owner=agent))`.

### 8.3 Adding a Custom Mental Faculty

Extend the mental faculty base to implement new cognitive operations (e.g., a "simulate_emotion" faculty) and register it with the agent.

### 8.4 Adding a Custom Environment

Subclass `TinyWorld` (or the base `TinyEnvironment`) to customize:

- Turn-taking logic
- Stimulus routing
- Spatial constraints
- Agent grouping

### 8.5 Extending Memory / Grounding

- **Custom memory connectors** — implement new grounding sources (documents, web pages) using LlamaIndex readers.
- **Custom consolidation** — override the consolidation pipeline to change how episodic memory is abstracted into semantic memory.

### 8.6 Custom Propositions for Validation

Create domain-specific propositions by subclassing `Proposition`:

```python
from tinytroupe.experimentation import Proposition

class CustomerSatisfactionProposition(Proposition):
    def __init__(self):
        super().__init__("The customer appears satisfied with the product")
```

Use these in `ActionGenerator` quality checks or post-hoc validation.

### 8.7 Custom Profiling Analysis

```python
profiler = Profiler()
profiler.add_custom_analysis(
    "sentiment_analysis",
    my_sentiment_function  # receives list of agents, returns analysis dict
)
profiler.profile(agents)
```

### 8.8 Persona Fragments

Create reusable persona mixins in JSON:

```json
// fragments/tech_enthusiast.agent.fragment.json
{
  "interests": ["AI", "gadgets", "programming"],
  "skills": ["Python", "system design"]
}
```

Merge into any base persona for rapid customization (see `examples/fragments/`).

---

## 9. Configuration Reference

Key `config.ini` parameters:

| Section | Key | Default | Purpose |
|---------|-----|---------|---------|
| `[OpenAI]` | `API_TYPE` | `openai` | Backend selector (`openai`/`azure`) |
| `[OpenAI]` | `MODEL` | `gpt-5-mini` | Primary text generation model |
| `[OpenAI]` | `REASONING_MODEL` | `o3-mini` | For precise reasoning tasks |
| `[OpenAI]` | `VISION_MODEL` | (falls back to `MODEL`) | Image understanding |
| `[OpenAI]` | `EMBEDDING_MODEL` | `text-embedding-3-small` | Semantic memory embeddings |
| `[OpenAI]` | `MAX_CONCURRENT_MODEL_CALLS` | `4` | Parallelism cap (`0`/`NONE` to disable) |
| `[Simulation]` | `PARALLEL_AGENT_ACTIONS` | `True` | Concurrent agent steps |
| `[Cognition]` | `ENABLE_MEMORY_CONSOLIDATION` | `True` | Episodic → semantic consolidation |
| `[Cognition]` | `MIN/MAX_EPISODE_LENGTH` | `10/15` | Memory chunk boundaries |
| `[ActionGenerator]` | `ENABLE_QUALITY_CHECKS` | `False` | Runtime action quality pipeline |
| `[ActionGenerator]` | `QUALITY_THRESHOLD` | `5` | Proposition pass score (0–9) |
| `[Logging]` | `LOGLEVEL` | `ERROR` | Root log level |

---

## 10. Testing & Experimentation

- **Unit tests:** `tests/unit/` — test individual components.
- **Scenario tests:** `tests/scenarios/` — end-to-end simulation scenarios.
- **Cache-based testing:** `test_with_cache.bat` — run tests using cached LLM responses for speed.
- **Empirical validation:** `data/empirical/` and `publications/` contain real-world comparison data and paper artifacts.

---

## 11. Extension Packages — `atamsim`

### Purpose

`atamsim` is a domain-specific extension package that implements the **Architecture Tradeoff Analysis Method (ATAM)** on top of the TinyTroupe framework. It demonstrates how TinyTroupe's core abstractions can be composed to create specialized, structured simulation workflows.

### ATAM → TinyTroupe mapping

| ATAM Concept | TinyTroupe Abstraction | atamsim Implementation |
|--------------|------------------------|------------------------|
| Stakeholder (Architect, QA Lead, Product Owner, …) | `TinyPerson` | Stakeholder generated from role templates via `ATAMStakeholderFactory` |
| Evaluation session | `TinyWorld` | `ATAMSession` orchestrates the multi-phase workflow |
| Stakeholder panel generation | `TinyPersonFactory` | `ATAMStakeholderFactory` extends with role-specific templates |
| Phase output extraction | `ResultsExtractor` | Specialized extractors (`ScenarioExtractor`, `ConcernExtractor`, `VoteExtractor`) |
| Final report | — | `ReportGenerator` aggregates phase outputs into an `ATAMReport` |

### Seven-phase workflow

```
1. Presentation           ── Architect presents the architecture to stakeholders
2. Approach Identification── Identify architectural approaches / patterns
3. Scenario Generation    ── Stakeholders generate use-case scenarios
4. Scenario Prioritization── Stakeholders vote on scenario importance
5. Approach Analysis      ── Analyze approaches against prioritized scenarios
6. Concern Identification ── Identify sensitivity points, tradeoffs, risks
7. Brainstorming          ── Generate mitigation strategies for concerns
```

Each phase is a plain Python orchestration object (`ATAMPhase` subclass) that drives stakeholder agents through the simulation, captures outputs, and feeds them into the next phase.

### Package structure

```
atamsim/
├── models.py               # Domain models (QualityAttribute, Scenario, Concern, …)
├── config.py               # atamsim-specific configuration loader
├── config.ini              # Separate config section for atamsim
├── session/atam_session.py # ATAMSession (TinyWorld subclass)
├── stakeholders/
│   ├── templates.py        # 10 predefined stakeholder role templates
│   └── stakeholder_factory.py  # ATAMStakeholderFactory
├── phases/                 # 7 phase implementations
│   ├── base_phase.py
│   ├── presentation_phase.py
│   └── …
├── extraction/             # Structured output extractors
│   ├── scenario_extractor.py
│   ├── concern_extractor.py
│   └── report_generator.py
├── prompts/                # Mustache templates for LLM prompts
├── data/                   # Sample architecture documents
└── tests/                  # Unit tests for domain models
```

### Key design decisions

1. **Separate package, not a fork** — `atamsim` lives alongside `tinytroupe/` and imports from it, rather than modifying core abstractions.
2. **Phase orchestration over subclassing** — Phases are plain Python objects that drive agents, not simulation entities. This keeps the simulation loop simple and the workflow logic explicit.
3. **Extraction by composition** — Extractors wrap `ResultsExtractor` rather than subclassing it, preserving the base API while adding domain-specific parsing.
4. **Pydantic for structured output** — Each extractor defines a Pydantic model (e.g., `ScenariosExtractionModel`) passed as `response_format` to the LLM client, ensuring JSON schema compliance.
5. **Template-driven stakeholders** — The 10 role templates (`templates.py`) provide rich persona seeds (Architect, Product Owner, QA Lead, Security Specialist, …) that the factory expands into full `TinyPerson` instances.
6. **Separate configuration** — `atamsim/config.ini` is layered on top of the base `config.ini`, keeping domain parameters isolated.

### Supported quality attributes

`QualityAttribute` enum covers 11 values: **Availability**, **Modifiability**, **Performance**, **Security**, **Testability**, **Usability**, **Scalability**, **Reliability**, **Deployability**, **Cost**.

### Concern taxonomy

Concerns are classified into four types — **SensitivityPoint**, **Tradeoff**, **Risk**, **NonRisk** — matching the standard ATAM output structure.

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **TinyPerson** | An LLM-powered synthetic persona with memory and cognition |
| **TinyWorld** | A simulated environment hosting agents |
| **Episode** | A chunk of episodic memory (stimuli + actions over a period) |
| **Transaction** | A cached, replayable unit of simulation state change |
| **Proposition** | An LLM-scored (0–9) claim about agent behavior |
| **Fragment** | A reusable persona mixin (JSON) |
| **Faculty** | A composable cognitive capability (perceive, reason, etc.) |

---

*This document reflects the architecture as of the current repository state. For the latest API details, see `docs/api/`.*