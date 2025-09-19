# nushell-verifier

A CLI tool to check NuShell script compatibility with different NuShell versions.

## Features

- **Automated Script Discovery**: Recursively scans directories for `.nu` files and shebang-identified scripts
- **Version Detection**: Multiple methods to determine last compatible version:
  - Comment headers in scripts (`# nushell-compatible-with: 0.95.0`)
  - Directory-level version files (`.compatible-nushell-version`)
  - Smart defaults (6 minor versions behind current)
- **GitHub Integration**: Fetches release notes and blog posts from NuShell repository
- **AI-Powered Analysis**: Uses LLM to convert release notes to compatibility checks and analyze scripts
- **Automatic Updates**: Updates version comments in compatible scripts
- **Comprehensive Reporting**: Detailed compatibility reports with suggested fixes

## Installation

### Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- [mise](https://mise.jdx.dev/) (optional, for Python version management)

### Using uv (recommended)

```bash
git clone <repository-url>
cd nushell-verifier
uv sync
```

### Using pip

```bash
git clone <repository-url>
cd nushell-verifier
pip install -e .
```

## Configuration

The tool uses XDG-compliant configuration. Create a config file at:
- `~/.config/nushell-verifier/config.toml` (Linux/macOS)
- Or use `--config` flag to specify a custom location

### Example Configuration

```toml
# LLM Provider configuration
llm_provider = "openai"  # or "anthropic", "google", etc.
llm_model = "gpt-4"
api_key = "your-api-key-here"

# Optional GitHub token for higher rate limits
# If not specified, the tool will try to use GitHub CLI token (gh auth token)
github_token = "your-github-token"

# Default directories to scan (optional)
scan_directories = [
    "~/dots/bin",
    "~/dots/config/nushell",
    "~/scripts"
]

# LLM parameters (optional)
temperature = 0.1  # Controls randomness (0.0-1.0), omitted for models that don't support it

# Advanced LLM parameters (optional)
[llm_params]
top_p = 0.9        # Nucleus sampling parameter
max_tokens = 4000  # Override default max tokens

# Caching (optional)
cache_enabled = true  # Enable/disable instruction caching (default: true)
```

### GitHub Authentication

The tool automatically detects GitHub authentication in this priority order:

1. **Configuration file**: If `github_token` is specified in the config file
2. **GitHub CLI**: If GitHub CLI (`gh`) is installed and authenticated, uses `gh auth token`
3. **No authentication**: Falls back to unauthenticated requests (subject to rate limits)

To set up GitHub CLI authentication:
```bash
gh auth login
```

### LLM Model Compatibility

The tool automatically handles parameter compatibility for different LLM models:

**Supported Models with Full Parameters:**
- OpenAI: `gpt-3.5-turbo`, `gpt-4`, `gpt-4-turbo`, `gpt-4o`, `gpt-4o-mini`
- Anthropic: `claude-3-sonnet`, `claude-3-opus`, `claude-3-haiku`, `claude-3-5-sonnet`
- Google: `gemini-pro`, `gemini-1.5-pro`

**Limited Parameter Support:**
- OpenAI: `gpt-5` (no temperature control - uses model default)

**Parameter Handling:**
- Unsupported parameters are automatically filtered out
- Default values are used when parameters aren't specified
- Custom parameters in config override defaults

## Usage

### Basic Usage

```bash
# Check compatibility with latest NuShell version
nushell-verifier

# Check compatibility with specific version
nushell-verifier --version 0.95.0

# Scan specific directories
nushell-verifier --directory ~/scripts --directory ~/bin

# Verbose output
nushell-verifier --verbose

# Progress control
nushell-verifier --no-progress   # Disable progress bars and spinners

# Cache management
nushell-verifier --cache-info    # Show cache statistics
nushell-verifier --clear-cache   # Clear all cached data
nushell-verifier --no-cache      # Bypass cache for this run
```

### Version Detection Methods

The tool determines the last compatible version for each script using this priority order:

1. **Comment Header**: Look for `# nushell-compatible-with: 0.95.0` in the script header
2. **Directory File**: Check for `.compatible-nushell-version` file in script directory or parent directories
3. **Default Assumption**: Use 6 minor versions behind the target version

### Example Script with Version Comment

```nushell
#!/usr/bin/env nu

# nushell-compatible-with: 0.95.0

# Your script content here
echo "Hello from NuShell!"
```

## How It Works

1. **Script Discovery**: Recursively scans specified directories for NuShell scripts
2. **Version Analysis**: Determines the last compatible version for each script
3. **Release Fetching**: Gets GitHub releases and blog posts between earliest and target versions
4. **AI Processing**: Converts blog posts to compatibility checking instructions using LLM
5. **Script Analysis**: Analyzes each script against breaking changes using LLM with real-time progress
6. **Immediate Feedback**: Shows compatibility results for each script as soon as analysis completes
7. **Reporting**: Generates detailed compatibility report with issues and fixes
8. **Auto-Update**: Updates version comments in compatible scripts

## Caching

The tool automatically caches compatibility instructions to improve performance:

**Benefits:**
- Significantly faster subsequent runs
- Reduced LLM API costs
- Reduced GitHub API requests

**How it works:**
- Compatibility instructions are cached per NuShell version and LLM model
- Cache files are stored in XDG-compliant directory (`~/.cache/nushell-verifier/`)
- Cache persists until manually cleared or model changes
- Each version/model combination gets its own cache file

**Cache Management:**
```bash
# View cache information
nushell-verifier --cache-info

# Clear all cached data
nushell-verifier --clear-cache

# Bypass cache for fresh analysis
nushell-verifier --no-cache
```

**Cache Location:**
The cache directory path is shown in `--cache-info` output. You can manually delete individual cache files if needed, or use `--clear-cache` to remove everything.

## Real-time Progress and Feedback

The tool provides real-time progress feedback during analysis:

**Features:**
- **Interactive Progress Bars**: Live progress indication for each script being analyzed
- **Token Streaming**: Real-time display of LLM token generation progress (when supported)
- **Immediate Results**: Compatibility results shown immediately after each script analysis
- **Batch Progress**: Overall progress tracking across multiple scripts
- **Processing Speed**: Live tokens per second metrics during analysis

**Progress Display:**
```
📄 [1/3] script1.nu | Phase: Analyzing compatibility | Tokens: 45/150 (30%) | 25 tok/s
✅ script1.nu - Compatible with 0.97.0

📄 [2/3] script2.nu | Phase: Analyzing compatibility | Tokens: 80/120 (67%) | 30 tok/s
⚠️  script2.nu - 2 issue(s) found
   📋 Issues found in script2.nu:
   ❌ Usage of deprecated `str collect` command
      💡 Fix: Replace `str collect` with `str join`

📊 Processed 3/3 scripts in 12.3s (avg: 4.1s per script)
```

**Progress Control:**
```bash
# Disable all progress bars and spinners (useful for CI/automation)
nushell-verifier --no-progress

# Normal operation with full progress feedback
nushell-verifier --verbose
```

**Technical Details:**
- Progress bars use the `alive-progress` library for smooth animations
- Token-level progress tracking works with streaming-capable LLM providers
- Automatic fallback to non-streaming mode when streaming is unavailable
- Progress estimation based on script size and complexity
- Batch processing with individual script progress tracking

## Dependencies

- **litellm**: Multi-provider LLM client
- **httpx**: HTTP client for GitHub API
- **click**: CLI framework
- **toml**: Configuration file parsing
- **alive-progress**: Real-time progress bars and spinners

## Development

### Setup Development Environment

```bash
# Install mise for Python version management
mise use python@3.13

# Install dependencies
uv sync

# Run tests
uv run pytest

# Run the CLI
uv run nushell-verifier --help
```

### Project Structure

```
nushell-verifier/
   src/nushell_verifier/
      __init__.py           # Package initialization
      main.py              # Entry point
      cli.py               # CLI interface
      config.py            # Configuration management
      models.py            # Data models
      scanner.py           # Script file scanner
      version_manager.py   # Version handling
      github_client.py     # GitHub API client
      llm_client.py        # LLM integration
      analyzer.py          # Main analysis logic
      reporter.py          # Report generation
   tests/                   # Test suite
   pyproject.toml          # Project configuration
   README.md               # This file
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

[Your license here]
