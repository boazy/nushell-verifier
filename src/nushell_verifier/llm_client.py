import litellm
from typing import Optional, List, Dict, Any, Callable
from .models import Config, ReleaseInfo, ScriptFile, CompatibilityIssue


class LLMClient:
    """Client for interacting with LLM providers via LiteLLM."""

    # Model parameter compatibility mapping
    MODEL_PARAM_COMPATIBILITY = {
        # OpenAI models
        "openai/gpt-3.5-turbo": {"temperature": True, "max_tokens": True, "top_p": True},
        "openai/gpt-4": {"temperature": True, "max_tokens": True, "top_p": True},
        "openai/gpt-4-turbo": {"temperature": True, "max_tokens": True, "top_p": True},
        "openai/gpt-4o": {"temperature": True, "max_tokens": True, "top_p": True},
        "openai/gpt-4o-mini": {"temperature": True, "max_tokens": True, "top_p": True},
        "openai/gpt-5": {"temperature": False, "max_tokens": True, "top_p": True},  # GPT-5 only supports temperature=1

        # Anthropic models
        "anthropic/claude-3-sonnet": {"temperature": True, "max_tokens": True, "top_p": True},
        "anthropic/claude-3-opus": {"temperature": True, "max_tokens": True, "top_p": True},
        "anthropic/claude-3-haiku": {"temperature": True, "max_tokens": True, "top_p": True},
        "anthropic/claude-3-5-sonnet": {"temperature": True, "max_tokens": True, "top_p": True},

        # Google models
        "google/gemini-pro": {"temperature": True, "max_tokens": True, "top_p": True},
        "google/gemini-1.5-pro": {"temperature": True, "max_tokens": True, "top_p": True},

        # Default fallback for unknown models
        "_default": {"temperature": False, "max_tokens": True, "top_p": False}
    }

    def __init__(self, config: Config):
        """Initialize LLM client with configuration."""
        self.config = config
        self.model = f"{config.llm_provider}/{config.llm_model}"

        # Set API key for the provider
        if config.api_key:
            if config.llm_provider == "openai":
                import os
                os.environ["OPENAI_API_KEY"] = config.api_key
            elif config.llm_provider == "anthropic":
                import os
                os.environ["ANTHROPIC_API_KEY"] = config.api_key
            elif config.llm_provider == "google":
                import os
                os.environ["GOOGLE_API_KEY"] = config.api_key
            # Add other providers as needed

    def _get_safe_params(self, custom_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get safe parameters for the current model."""
        params = {}

        # Get model compatibility or use default
        model_compat = self.MODEL_PARAM_COMPATIBILITY.get(
            self.model,
            self.MODEL_PARAM_COMPATIBILITY["_default"]
        )

        # Add temperature if supported
        if model_compat.get("temperature", False):
            if self.config.temperature is not None:
                params["temperature"] = self.config.temperature
            else:
                params["temperature"] = 0.1  # Default for deterministic results

        # Add max_tokens if supported (high limit for modern models processing large blog posts)
        if model_compat.get("max_tokens", False):
            params["max_tokens"] = 32000

        # Merge custom parameters
        if custom_params:
            for key, value in custom_params.items():
                if model_compat.get(key, False):
                    params[key] = value

        # Merge user-configured parameters
        for key, value in self.config.llm_params.items():
            if model_compat.get(key, False):
                params[key] = value

        return params

    def convert_blog_to_instructions(self, release: ReleaseInfo, blog_content: str) -> str:
        """Convert blog post content to compatibility checking instructions."""
        prompt = f"""
You are a NuShell expert analyzing release notes. Your task is to convert the blog post content for NuShell {release.version} into a set of specific, actionable instructions for checking if existing NuShell scripts are compatible with this version.

Focus on:
1. Breaking changes that affect script syntax or behavior
2. Deprecated features and their replacements
3. New syntax requirements or restrictions
4. Changes to built-in commands or their parameters
5. Changes to variable scoping or data types

For each breaking change, provide:
- A clear description of what changed
- How to detect if a script uses the old pattern
- What the new pattern should be

Ignore:
- New features that don't affect existing scripts
- Performance improvements
- Bug fixes that don't change expected behavior
- Documentation updates

Blog post content:
{blog_content}

Please provide the output as a structured list of compatibility checks:
"""

        try:
            params = self._get_safe_params()
            response = litellm.completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                **params
            )

            result = response.choices[0].message.content
            if result is None:
                print(f"  Warning: LLM returned None content for {release.version}")
                return ""

            return result.strip()
        except Exception as e:
            raise RuntimeError(f"Failed to process blog post for {release.version}: {e}")

    def analyze_script_compatibility(
        self,
        script: ScriptFile,
        target_version: str,
        compatibility_instructions: List[str]
    ) -> List[CompatibilityIssue]:
        """Analyze script compatibility against breaking changes."""
        # Read script content
        try:
            with open(script.path, "r", encoding="utf-8", errors="ignore") as f:
                script_content = f.read()
        except (OSError, UnicodeDecodeError) as e:
            raise RuntimeError(f"Failed to read script {script.path}: {e}")

        # Combine all compatibility instructions
        all_instructions = "\n\n".join(compatibility_instructions)

        prompt = f"""
You are a NuShell expert analyzing script compatibility. Review the following NuShell script against the compatibility requirements for version {target_version}.

Script path: {script.path}
Last known compatible version: {script.compatible_version}
Target version: {target_version}

Compatibility requirements to check:
{all_instructions}

Script content:
```nushell
{script_content}
```

Analyze the script and identify any compatibility issues. For each issue found, provide:
1. A clear description of the problem
2. The specific line(s) or pattern that causes the issue
3. A suggested fix or replacement
4. The severity level (error, warning, info)

If the script is fully compatible, respond with "COMPATIBLE".

Format your response as a JSON array of issues:
[
  {{
    "description": "Clear description of the issue",
    "suggested_fix": "How to fix it",
    "severity": "error|warning|info"
  }}
]

Or simply: COMPATIBLE
"""

        try:
            params = self._get_safe_params()
            response = litellm.completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                **params
            )

            result = response.choices[0].message.content.strip()

            if result == "COMPATIBLE":
                return []

            # Parse JSON response
            import json
            try:
                issues_data = json.loads(result)
                return [
                    CompatibilityIssue(
                        description=issue["description"],
                        suggested_fix=issue.get("suggested_fix"),
                        severity=issue.get("severity", "warning")
                    )
                    for issue in issues_data
                ]
            except json.JSONDecodeError:
                # Fallback: treat entire response as a single issue
                return [CompatibilityIssue(
                    description=result,
                    severity="warning"
                )]

        except Exception as e:
            raise RuntimeError(f"Failed to analyze script {script.path}: {e}")

    def convert_blog_to_instructions_streaming(
        self,
        release: ReleaseInfo,
        blog_content: str,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> str:
        """Convert blog post content to compatibility checking instructions with streaming.

        Args:
            release: Release information
            blog_content: Blog post content
            progress_callback: Optional callback for progress updates

        Returns:
            Compatibility checking instructions
        """
        prompt = f"""
You are a NuShell expert analyzing release notes. Your task is to convert the blog post content for NuShell {release.version} into a set of specific, actionable instructions for checking if existing NuShell scripts are compatible with this version.

Focus on:
1. Breaking changes that affect script syntax or behavior
2. Deprecated features and their replacements
3. New syntax requirements or restrictions
4. Changes to built-in commands or their parameters
5. Changes to variable scoping or data types

For each breaking change, provide:
- A clear description of what changed
- How to detect if a script uses the old pattern
- What the new pattern should be

Ignore:
- New features that don't affect existing scripts
- Performance improvements
- Bug fixes that don't change expected behavior
- Documentation updates

Blog post content:
{blog_content}

Please provide the output as a structured list of compatibility checks:
"""

        try:
            # Try streaming first, fallback to regular completion
            try:
                return self._stream_completion(prompt, progress_callback)
            except Exception:
                # Fallback to non-streaming
                params = self._get_safe_params()
                response = litellm.completion(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    **params
                )
                result = response.choices[0].message.content
                if result is None:
                    print(f"  Warning: LLM returned None content for {release.version}")
                    return ""
                return result.strip()

        except Exception as e:
            raise RuntimeError(f"Failed to process blog post for {release.version}: {e}")

    def analyze_script_compatibility_streaming(
        self,
        script: ScriptFile,
        target_version: str,
        compatibility_instructions: List[str],
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> List[CompatibilityIssue]:
        """Analyze script compatibility against breaking changes with streaming.

        Args:
            script: Script file information
            target_version: Target NuShell version
            compatibility_instructions: List of compatibility instructions
            progress_callback: Optional callback for progress updates

        Returns:
            List of compatibility issues found
        """
        # Read script content
        try:
            with open(script.path, "r", encoding="utf-8", errors="ignore") as f:
                script_content = f.read()
        except (OSError, UnicodeDecodeError) as e:
            raise RuntimeError(f"Failed to read script {script.path}: {e}")

        # Combine all compatibility instructions
        all_instructions = "\n\n".join(compatibility_instructions)

        prompt = f"""
You are a NuShell expert analyzing script compatibility. Review the following NuShell script against the compatibility requirements for version {target_version}.

Script path: {script.path}
Last known compatible version: {script.compatible_version}
Target version: {target_version}

Compatibility requirements to check:
{all_instructions}

Script content:
```nushell
{script_content}
```

Analyze the script and identify any compatibility issues. For each issue found, provide:
1. A clear description of the problem
2. The specific line(s) or pattern that causes the issue
3. A suggested fix or replacement
4. The severity level (error, warning, info)

If the script is fully compatible, respond with "COMPATIBLE".

Format your response as a JSON array of issues:
[
  {{
    "description": "Clear description of the issue",
    "suggested_fix": "How to fix it",
    "severity": "error|warning|info"
  }}
]

Or simply: COMPATIBLE
"""

        try:
            # Try streaming first, fallback to regular completion
            try:
                result = self._stream_completion(prompt, progress_callback)
            except Exception:
                # Fallback to non-streaming
                params = self._get_safe_params()
                response = litellm.completion(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    **params
                )
                result = response.choices[0].message.content.strip()

            if result == "COMPATIBLE":
                return []

            # Parse JSON response
            import json
            try:
                issues_data = json.loads(result)
                return [
                    CompatibilityIssue(
                        description=issue["description"],
                        suggested_fix=issue.get("suggested_fix"),
                        severity=issue.get("severity", "warning")
                    )
                    for issue in issues_data
                ]
            except json.JSONDecodeError:
                # Fallback: treat entire response as a single issue
                return [CompatibilityIssue(
                    description=result,
                    severity="warning"
                )]

        except Exception as e:
            raise RuntimeError(f"Failed to analyze script {script.path}: {e}")

    def _stream_completion(
        self,
        prompt: str,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> str:
        """Perform streaming completion with progress updates.

        Args:
            prompt: The prompt to send to the LLM
            progress_callback: Optional callback for token updates

        Returns:
            Complete response content
        """
        params = self._get_safe_params()

        # Add streaming parameters
        params.update({
            "stream": True,
            "stream_options": {"include_usage": True}
        })

        response = litellm.completion(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            **params
        )

        # Collect the streamed response
        content_parts = []

        for chunk in response:
            # Handle different chunk types
            if hasattr(chunk, 'choices') and chunk.choices:
                delta = chunk.choices[0].delta

                if hasattr(delta, 'content') and delta.content:
                    content_parts.append(delta.content)

                    # Call progress callback if provided
                    if progress_callback:
                        try:
                            progress_callback(delta.content)
                        except Exception:
                            # Don't let callback errors break streaming
                            pass

            # Handle usage information if available
            if hasattr(chunk, 'usage') and chunk.usage:
                # This is the final chunk with usage info
                if progress_callback:
                    try:
                        # Send usage info as a special callback
                        progress_callback(f"__USAGE__{chunk.usage}")
                    except Exception:
                        pass

        return ''.join(content_parts).strip()