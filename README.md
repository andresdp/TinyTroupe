# TinyTroupe for ATAM Simulation

> **Fork of [microsoft/TinyTroupe](https://github.com/microsoft/TinyTroupe)** — used as the simulation engine foundation for an **ATAM (Architecture Tradeoff Analysis Method)** multi-agent extension.

---

## What is TinyTroupe?

[TinyTroupe](https://github.com/microsoft/TinyTroupe) is an experimental Python library for **LLM-powered multi-agent persona simulation**. It lets you define synthetic people (`TinyPerson`), place them in simulated environments (`TinyWorld`), and have them perceive stimuli, reason, and act — producing realistic conversational and behavioral traces. This fork vendors the core engine (v0.7.0) unchanged.

## What is the ATAM extension?

The [Architecture Tradeoff Analysis Method (ATAM)](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=519528) is a structured method for evaluating software architectures against quality-attribute requirements through stakeholder participation. The goal of this fork is to extend TinyTroupe so that ATAM evaluation sessions can be run as **multi-agent simulations**: each stakeholder is an AI agent with a role-specific persona, and the evaluation phases (scenario generation, prioritization, risk identification, etc.) are orchestrated as simulation steps.

This lets us run preliminary or exploratory architecture evaluations **without requiring human stakeholder availability**.

## Current status

| Component | Status |
|-----------|--------|
| `tinytroupe/` core engine | ✅ Vendored from upstream v0.7.0, fully functional |
| `tests/` | ✅ Core unit and scenario tests working |
| `atamsim/` extension | 🔲 In planning / skeleton only |

The core `tinytroupe` package can be imported and used directly. The ATAM extension is not yet implemented.

## Installation

This package is installed directly from the repository — it is **not** published to PyPI.

```bash
# 1. Clone
git clone https://github.com/andresdp/TinyTroupe.git
cd TinyTroupe

# 2. Create environment (Python 3.10+)
conda create -n tinytroupe python=3.10
conda activate tinytroupe

# 3. Set your OpenAI API key
export OPENAI_API_KEY="your-key-here"   # Linux/macOS
# $env:OPENAI_API_KEY="your-key-here"    # Windows PowerShell

# 4. Install
pip install .

# Or, for development:
pip install -e .
```

You can verify the install:

```python
import tinytroupe
from tinytroupe.agent import TinyPerson
from tinytroupe.environment import TinyWorld
```

### Configuration

Copy `config.ini` to your working directory and adjust as needed. Key settings:

| Section | Key | Default | Purpose |
|---------|-----|---------|---------|
| `[OpenAI]` | `MODEL` | `gpt-5-mini` | Primary LLM model |
| `[OpenAI]` | `API_TYPE` | `openai` | `openai` or `azure` |
| `[Simulation]` | `PARALLEL_AGENT_ACTIONS` | `True` | Concurrent agent steps |
| `[Cognition]` | `ENABLE_MEMORY_CONSOLIDATION` | `True` | Episodic → semantic memory |

## Usage

The two core abstractions are `TinyPerson` (agents) and `TinyWorld` (environments):

```python
from tinytroupe.factory import TinyPersonFactory
from tinytroupe.environment import TinyWorld

# Generate a stakeholder persona
factory = TinyPersonFactory(context="A software architecture review team.")
architect = factory.generate_person("A senior software architect focused on scalability.")

# Create a session environment and run
world = TinyWorld("Architecture Review", [architect])
world.make_everyone_accessible()
world.broadcast("Please introduce yourself and your main architectural concerns.")
world.run(3)
```

For the full upstream API (tools, validators, extractors, profiling, empirical validation), see the [upstream documentation](https://github.com/microsoft/TinyTroupe).

## Architecture

For a detailed architectural overview of the `tinytroupe` core engine, see [`docs/high_level_design.md`](./docs/high_level_design.md).

## Credits

TinyTroupe was created by **Paulo Salem** (lead), Christopher Olsen, Yi Ding, and Prerit Saxena at Microsoft Research. See the [upstream acknowledgements](https://github.com/microsoft/TinyTroupe#acknowledgements) for the full list of contributors.

This fork is maintained for research purposes related to ATAM simulation.

## License

MIT License — see [`LICENSE`](./LICENSE). This is a fork of Microsoft's open-source release; all upstream terms apply.