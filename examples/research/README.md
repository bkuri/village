# Research Domain Extension Example

This example demonstrates how to extend Village's chat loop for academic research use cases, showcasing the extensibility framework's flexibility beyond trading domains.

## Quick Start

### 1. Load Extensions Programmatically

```python
from examples.research.chat import bootstrap_research_extensions
from village.extensibility import initialize_extensions

# Bootstrap research extensions
registry = bootstrap_research_extensions()

# Initialize extensions from config
initialize_extensions(registry, "examples/research/config.example.toml")
```

### 2. Load Extensions via Configuration

Create a `config.toml` file with extension paths:

```toml
[extensions]
processor_module = "examples.research.chat.processors:ResearchChatProcessor"
thinking_refiner_module = "examples.research.chat.thinking_refiners:ResearchThinkingRefiner"
tool_invoker_module = "examples.research.chat.tool_invokers:ResearchToolInvoker"
chat_context_module = "examples.research.chat.context:ResearchChatContext"
beads_integrator_module = "examples.research.chat.beads_integrators:ResearchBeadsIntegrator"
```

Then initialize:

```python
from village.extensibility import initialize_extensions
from village.extensibility import ExtensionRegistry

registry = ExtensionRegistry()
initialize_extensions(registry, "config.toml")
```

## Example Usage

### Research Query Breakdown

**Input:**
```
Research machine learning interpretability
```

**Thinking Refiner Output:**
The query is broken into systematic steps:
1. Define the research question: Research machine learning interpretability
2. Identify key terms, concepts, and search queries
3. Search academic databases (Google Scholar, arXiv, etc.)
4. Analyze and synthesize findings from multiple sources
5. Generate citations and bibliography in appropriate format

**Context Hints:**
- `required_data_sources`: ["knowledge_store", "perplexity"]
- `domain_context.research_field`: "Machine Learning"

### Comparison Query

**Input:**
```
Compare supervised vs reinforcement learning
```

**Processor Pre-processing:**
- Normalizes query format
- Adds "Research" prefix if needed

**Thinking Refiner Output:**
Systematic comparison steps with methodology context.

### Literature Search

**Input:**
```
Find papers on LLM safety
```

**Tool Invoker:**
- Caches query to avoid redundant searches
- Logs query to console: `[RESEARCH] Logged query: Find papers on LLM safety`
- Adds default methodology: `systematic_review`

**Beads Integration:**
Creates a Beads task with metadata:
- `research_field`: "Large Language Models"
- `methodology`: "mixed"
- `tags`: ["research", "large_language_models"]

## Extension Points Demonstrated

### 1. ChatProcessor (`processors.py`)

**Pre-processing:**
- Extracts research topics and questions
- Normalizes research query format
- Adds "Research" prefix if missing

**Post-processing:**
- Formats citations (APA, MLA, Chicago)
- Adds source metadata to responses
- Detects citation patterns: `[1]`, `(Smith, 2024)`, `(Smith et al. 2024)`

### 2. ThinkingRefiner (`thinking_refiners.py`)

**should_refine():**
- Returns `True` for research queries
- Detects keywords: research, study, investigate, analyze, compare, etc.

**refine_query():**
- Breaks queries into 5 systematic steps:
  1. Define research question
  2. Identify key terms and concepts
  3. Search academic databases
  4. Analyze and synthesize findings
  5. Generate citations and bibliography
- Extracts research field (ML, NLP, CV, etc.)
- Sets `required_data_sources` and `domain_context`

### 3. ToolInvoker (`tool_invokers.py`)

**should_invoke():**
- Checks cache for research queries
- Avoids redundant searches

**transform_args():**
- Adds default methodology if not specified
- Enriches research tool arguments

**on_success():**
- Logs all research queries to console (audit trail)
- Caches results for future reference

**on_error():**
- Logs tool errors for debugging

### 4. ChatContext (`context.py`)

**load_context():**
- Returns empty `SessionContext` (minimal)

**enrich_context():**
- Adds timestamp to context
- Adds session info (session_id, session_type: "research")

**save_context():**
- No-op (minimal implementation)

### 5. BeadsIntegrator (`beads_integrators.py`)

**should_create_bead():**
- Returns `True` for research tasks
- Detects "research" in task_type or context

**create_bead_spec():**
- Creates `BeadSpec` with metadata:
  - `research_field`: Academic domain
  - `methodology`: qualitative/quantitative/mixed
  - `sources`: Number of sources cited
  - `citation_style`: "APA"
- Adds tags: ["research", field_name]

**on_bead_created():**
- Logs bead creation to console
- Extracts research field from metadata

**on_bead_updated():**
- No-op (minimal implementation)

## Configuration Options

```toml
[research]
# Citation format: APA, MLA, Chicago
citation_style = "APA"

# Default research methodology
default_methodology = "mixed"

# Enable query caching (in-memory)
enable_query_cache = true

# Audit trail settings
log_research_queries = true
log_bead_creation = true

# Data sources for research queries
data_sources = ["knowledge_store", "perplexity"]
```

## Architecture

```
examples/research/
├── __init__.py              # Package initialization
├── chat/
│   ├── __init__.py         # Chat package init
│   ├── processors.py       # ResearchChatProcessor
│   ├── thinking_refiners.py # ResearchThinkingRefiner
│   ├── tool_invokers.py     # ResearchToolInvoker
│   ├── context.py           # ResearchChatContext
│   ├── beads_integrators.py # ResearchBeadsIntegrator
│   └── bootstrap.py        # Bootstrap function
├── config.example.toml     # Configuration example
└── README.md               # This file
```

## Implementation Details

### Research Field Extraction

The system automatically detects research fields from queries:

| Query Text | Detected Field |
|------------|----------------|
| "machine learning" | Machine Learning |
| "deep learning" | Deep Learning |
| "nlp" | Natural Language Processing |
| "computer vision" | Computer Vision |
| "ai safety" | AI Safety |
| "reinforcement learning" | Reinforcement Learning |
| "llm" | Large Language Models |

### Methodology Detection

Analyzes query text to determine research approach:

**Qualitative:**
- Keywords: qualitative, interview, case study, survey

**Quantitative:**
- Keywords: quantitative, experiment, statistical, data

**Mixed:**
- Default when no clear indicators

### Citation Formatting

Supports multiple citation styles:

**APA:**
```
(Smith, 2024) -> (Source 1)
```

**MLA:**
```
[Smith 2024] -> [1]
```

## Testing the Example

```python
# Test processor
from examples.research.chat.processors import ResearchChatProcessor

processor = ResearchChatProcessor(citation_style="APA")
query = "research machine learning"
processed = await processor.pre_process(query)
print(processed)  # "Research machine learning"

# Test thinking refiner
from examples.research.chat.thinking_refiners import ResearchThinkingRefiner

refiner = ResearchThinkingRefiner()
should_refine = await refiner.should_refine(query)
print(should_refine)  # True

refinement = await refiner.refine_query(query)
print(refinement.refined_steps)
# [
#   "Define the research question: research machine learning",
#   "Identify key terms, concepts, and search queries",
#   ...
# ]

# Test bootstrap
from examples.research.chat import bootstrap_research_extensions

registry = bootstrap_research_extensions()
print(f"Registered {len(registry._processors)} processors")  # 1
```

## Key Features Demonstrated

1. **Domain-Specific Query Processing**
   - Research topic extraction
   - Query normalization
   - Citation formatting

2. **Systematic Research Methodology**
   - Step-by-step query breakdown
   - Research field detection
   - Data source hints

3. **Query Optimization**
   - In-memory caching
   - Redundant search prevention
   - Audit trail logging

4. **Task Integration**
   - Beads task creation
   - Research metadata
   - Tag-based organization

5. **Minimal Configuration**
   - No external dependencies
   - File-based config
   - Simple bootstrap function

## Extending Further

To extend this example for your own domain:

1. **Create new extension classes** inheriting from ABCs
2. **Implement required methods** for each extension point
3. **Configure paths** in your `config.toml`
4. **Bootstrap extensions** in your application

See the [Village extensibility documentation](../../village/extensibility/__init__.py) for full API details.

## License

This example is part of Village. See the project LICENSE for details.
