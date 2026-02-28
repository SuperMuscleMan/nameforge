# AGENTS.md

This file provides guidance to Qoder (qoder.com) when working with code in this repository.

## Project Overview

A Python 3.10+ CLI application for AI-powered game nickname generation using LLM APIs (currently Alibaba Cloud Qwen). Generates unique usernames in styles like 古风 (Ancient Chinese), 二次元 (Anime), and 赛博朋克 (Cyberpunk).

## Build/Test Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application (requires API key)
export GLM_API_KEY='your_key'
python src/main.py

# Run with specific style and count
python src/main.py --style 古风 --count 100

# Regenerate word roots (delete old and regenerate)
python src/main.py --regenerate-roots --style 古风

# Run demo (uses Mock API, no key needed)
python demo.py

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_config_manager.py -v
pytest tests/test_integration.py -v

# Run specific test function
pytest tests/test_config_manager.py::TestConfigManager::test_load_styles -v

# Start Redis (for Phase 3 deduplication)
docker-compose up -d redis
```

## Architecture

### Component Structure

The codebase follows a modular pipeline architecture:

- **ConfigManager** (`src/config/config_manager.py`): YAML configuration with hot-reload support. Watches file mtime and auto-reloads on change. Supports environment variable substitution via `${VAR_NAME}` syntax.

- **GLMClient** (`src/api/glm_client.py`): API client for LLM calls. Implements single-threaded queue-based calling (no concurrency - free API key constraint) with exponential backoff retry (base interval configurable, default 10s). Currently configured for Alibaba Cloud Qwen API. `max_tokens` is configurable via `config.yaml`.

- **PromptManager** (`src/prompts/prompt_manager.py`): Jinja2-style template rendering for prompts. Substitutes placeholders like `{{ style_desc }}`, `{{ length_hint }}`, `{{ recent_names }}`.

- **WordRootManager** (`src/roots/word_root_manager.py`): Manages word root generation, storage, and loading. Generates roots via single API call for all categories. Stores roots to `data/{style}_roots.yaml`.

- **NicknameGenerator** (`src/generator/nickname_generator.py`): Generates nicknames by combining word roots using templates. Supports deduplication against existing names in storage.

- **GenerationPipeline** (`src/pipeline/generation_pipeline.py`): Orchestrates the complete workflow: Load config → Generate/Load word roots → Combine templates → Filter → Deduplicate → Store. Supports both V1 (direct API) and V2 (word root template) modes via `use_v2` parameter.

- **StorageManager** (`src/storage/storage_manager.py`): File-based persistence. Stores names to `data/{style}_names.txt` and metadata to `data/{style}_metadata.txt`.

### Configuration Files

- `config/config.yaml`: System settings (API endpoints, Redis, storage paths, logging, `api.glm.max_tokens`). API provider can be switched between glm/openai/claude.
- `config/styles.yaml`: Style definitions (description, length constraints, charset), word root categories, templates, and filter rules. Styles can be enabled/disabled via `enabled: true/false`.
- `data/{style}_roots.yaml`: Generated word roots for each style (auto-generated)

### Data Flow (V2 - Word Root Template)

1. Pipeline loads style config from `styles.yaml`
2. WordRootManager checks for existing roots in `data/{style}_roots.yaml`
3. If not exists, GLMClient generates all category roots in single API call
4. NicknameGenerator combines roots using templates (Cartesian product)
5. Filters applied: length check, duplicate char check, forbidden combinations
6. Deduplication against existing names in `data/{style}_names.txt`
7. StorageManager appends new names to file

### Data Flow (V1 - Legacy Direct Generation)

1. Pipeline loads style config from `styles.yaml`
2. PromptManager renders template with recent names (for deduplication hints)
3. GLMClient calls API with retry logic
4. Response parsed as JSON array: `["name1", "name2", ...]`
5. Names validated against length/charset constraints
6. StorageManager appends to file

### Testing

- 56 tests using pytest
- Mock API fixtures in `tests/fixtures/mock_responses.py` for reproducible testing
- Integration tests cover end-to-end workflows

### Project Phases

- **Phase 1** (Complete): Config management, prompt system, API client, file storage, tests
- **Phase 2** (Complete V2): Word root template generation, nickname generator, deduplication against existing names
- **Phase 3** (Planned): Redis deduplication, sensitive word filtering, APScheduler task scheduling
- **Phase 4** (Planned): Quality validation, monitoring, production deployment

## Important Notes

- API key required via `GLM_API_KEY` environment variable for real API calls
- Invalid JSON responses are logged to `logs/last_api_response_{style}.log`
- All text files use UTF-8 encoding (Chinese content)
- Logs rotate at 10MB with 5 backups
- Word roots are cached in memory and stored in `data/{style}_roots.yaml`
- Use `--regenerate-roots` to force regeneration of word roots if quality is poor
- NicknameGenerator deduplicates against existing names in `data/{style}_names.txt`
- GenerationPipeline defaults to V2 mode (`use_v2=True`); set to `False` for legacy V1 behavior
