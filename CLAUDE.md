# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Essential Commands

### Development Workflow
```bash
# Setup
uv sync                    # Install dependencies
mise trust && mise install # Setup tools

# Testing and Quality
mise test                  # Run full test suite (107 tests)
mise lint                  # Run ruff linting
python -m pytest tests/test_specific.py  # Run specific test file

# Run the application
uv run nushell-verifier --help
mise nv --help            # Alias for nushell-verifier
```

### Cache Management Commands
```bash
# New cache commands (refactored CLI structure)
nushell-verifier cache info          # Detailed view with rich formatting
nushell-verifier cache info --short  # Brief summary
nushell-verifier cache clean         # Clear all cached data
nushell-verifier cache add 0.107.0   # Pre-populate cache for specific versions
```

## Architecture Overview

### Core Analysis Flow
The application follows a pipeline architecture:
1. **Scanner** → **Version Manager** → **GitHub Client** → **LLM Client** → **Reporter**
2. **Instruction Cache** sits between GitHub/LLM for performance optimization

### Key Components

**NuShellAnalyzer** (`analyzer.py`): Central orchestrator that coordinates all components
- Manages the complete analysis workflow
- Handles caching logic for compatibility instructions
- Coordinates between script scanning, version detection, and LLM analysis

**Instruction Cache** (`cache.py`): Performance-critical caching system
- **Recent Refactor**: Filename structure changed from `{version}_{model}.json` to `{version}.json`
- Model information preserved in JSON metadata for future use
- Caches LLM-generated compatibility instructions per version
- Uses XDG-compliant directory structure

**CLI Structure** (`cli.py`): Multi-command CLI with subcommands
- **Main command**: Script analysis (invoke without subcommand)
- **Cache subcommands**: `info`, `clean`, `add` with rich formatting
- **Recent Addition**: `cache add` command for pre-populating instructions

### LLM Integration Pattern
The system uses a two-phase LLM approach:
1. **Instruction Generation**: Convert NuShell release blog posts to compatibility checking instructions
2. **Script Analysis**: Apply these instructions to analyze user scripts

### Configuration Management
- XDG-compliant config in `~/.config/nushell-verifier/config.toml`
- Auto-detection of GitHub tokens (config → gh CLI → unauthenticated)
- LLM provider abstraction through litellm with parameter compatibility handling

## Important Implementation Details

### Version Detection Hierarchy
Scripts are analyzed using this priority order:
1. Comment headers: `# nushell-compatible-with: 0.95.0`
2. Directory files: `.compatible-nushell-version`
3. Smart defaults: 6 minor versions behind target

### Cache Architecture
- **Cache Key**: `{version}.json` (model stored in JSON metadata)
- **Cache Logic**: Version + LLM model combination determines cache validity
- **Cache Location**: `~/.cache/nushell-verifier/instructions/`
- **Invalidation**: Manual only (`cache clean`) or model change

### Progress and Streaming
- Real-time progress bars using `alive-progress`
- Token-level streaming progress for supported LLM providers
- Immediate feedback as each script completes analysis
- `--no-progress` flag for CI/automation environments

## Testing Strategy

### Test Structure (107 tests total)
- **Unit tests**: Individual component testing
- **Integration tests**: Cross-component workflows (especially cache integration)
- **CLI tests**: Command-line interface validation
- **Progress tests**: Real-time feedback system validation

### After Making Changes
Always run both commands to ensure code quality:
```bash
mise test && mise lint
```

## Key Files and Responsibilities

**Core Logic:**
- `analyzer.py`: Main orchestration and workflow
- `llm_client.py`: LLM integration with streaming support
- `github_client.py`: Release and blog post fetching

**Data Flow:**
- `scanner.py`: Script discovery and initial metadata
- `version_manager.py`: Version comparison and compatibility logic
- `models.py`: Data structures (ScriptFile, ReleaseInfo, CompatibilityIssue, etc.)

**User Interface:**
- `cli.py`: Command-line interface with cache subcommands
- `reporter.py`: Output formatting and results presentation
- `progress.py`: Real-time progress tracking and streaming

**Infrastructure:**
- `cache.py`: Performance optimization through instruction caching
- `config.py`: Configuration management and XDG compliance

## Common Development Patterns

### Adding New CLI Commands
Use Click's group/command structure. Cache subcommands are in `cli.py` under the `@cache.group()`.

### Cache Operations
Always check cache first, then fallback to generation. The cache stores full LLM model info for future analysis.

### LLM Integration
Use the `LLMClient` abstraction which handles provider differences and parameter compatibility automatically.

### Testing Cache Changes
Pay special attention to `tests/test_cache_integration.py` and `tests/test_cache.py` when modifying cache behavior.
- # Always run mise test and mise lint after each set of todos to verify your changes.