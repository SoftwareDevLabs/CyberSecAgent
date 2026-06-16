## src folder

This directory contains all the relevants source code important to the software.

```
📁 src/ → The core engine — all logic lives here:
├── agents/ → Agent classes: planner, executor, base agent
│
├── memory/ → Short-term and long-term memory modules
│
├── pipelines/ → Chat flows, doc processing, and task routing
│
├── retrieval/ → Vector search and document lookup
│
├── skills/ → Extra abilities: web search, code execution
│
├── vision_audio/ → Multimodal processing: image and audio
│
├── prompt_engineering/→ Prompt chaining, templates, few-shot logic # Prompt engineering tools
│   ├── templates.py    # Template management
│   ├── few_shot.py    # Few-shot prompt utilities
│   └── chain.py       # Prompt chaining logic
│
├── config/ → YAML config for models, prompts, logging
│
├── llm/ → OpenAI, Anthropic, and custom LLM routing
│   ├── base.py         # Base LLM client
│   ├── claude_client.py # Anthropic Claude client
│   ├── gpt_client.py   # OpenAI GPT client
│   └── utils.py        # Shared utilities
│
├── llm_clients/ → LLM client implementations
│
├── fallback/ → Recovery logic when LLMs fail
│
├── guardrails/ → PII filters, output validation, safety checks
│
├── handlers/ → Input/output processing and error management
│   ├── error_handler.py   # Error handling utilities
│
└── utils/ → Logging, caching, rate limiting, token counting
     ├── rate_limiter.py # API rate limiting
     ├── token_counter.py # Token counting
     ├── cache.py       # Response caching
     └── logger.py      # Logging utilities

```

## Key Components

1. **LLM** (`src/llm/`)
   - Base client with common functionality
   - Specific implementations for different providers
   - Utility functions for token counting and rate limiting

2. **Prompt Engineering** (`src/prompt_engineering/`)
   - Template management system
   - Few-shot prompt utilities
   - Prompt chaining capabilities

3. **Utilities** (`src/utils/`)
   - Rate limiting for API calls
   - Token counting
   - Response caching
   - Logging
