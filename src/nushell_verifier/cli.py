import click
import litellm
from pathlib import Path
from typing import List, Optional


@click.command()
@click.option(
    "--version", "-v",
    help="NuShell version to check compatibility against (defaults to latest)"
)
@click.option(
    "--directory", "-d", "directories",
    multiple=True,
    help="Directory to scan for NuShell scripts (can be repeated)"
)
@click.option(
    "--config", "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file"
)
@click.option(
    "--verbose", "-V",
    is_flag=True,
    help="Enable verbose output"
)
@click.option(
    "--no-cache",
    is_flag=True,
    help="Bypass cache and fetch fresh data"
)
@click.option(
    "--clear-cache",
    is_flag=True,
    help="Clear all cached compatibility instructions and exit"
)
@click.option(
    "--cache-info",
    is_flag=True,
    help="Show cache information and exit"
)
@click.option(
    "--no-progress",
    is_flag=True,
    help="Disable progress bars and spinners"
)
@click.option(
    "--debug",
    is_flag=True,
    help="Debug mode"
)
def cli(
    version: Optional[str],
    directories: List[str],
    config: Optional[Path],
    verbose: bool,
    no_cache: bool,
    clear_cache: bool,
    cache_info: bool,
    no_progress: bool,
    debug: bool
):
    """NuShell script compatibility verifier.

    Scans NuShell scripts and checks their compatibility with specified or latest NuShell version.
    """
    from .config import load_config
    from .analyzer import NuShellAnalyzer
    from .reporter import Reporter
    from .cache import InstructionCache

    if debug:
        litellm._turn_on_debug()

    # Handle cache management commands first
    if cache_info or clear_cache:
        cache = InstructionCache()

        if cache_info:
            info = cache.get_cache_info()
            click.echo("Cache Information:")
            click.echo(f"  Directory: {info['cache_directory']}")
            click.echo(f"  Exists: {info['exists']}")
            click.echo(f"  Files: {info['file_count']}")
            if info['exists']:
                click.echo(f"  Total size: {info['total_size_mb']} MB")
                if info['versions']:
                    click.echo(f"  Cached versions: {', '.join(info['versions'])}")
                else:
                    click.echo("  No cached versions")
            return

        if clear_cache:
            removed_count = cache.clear_cache()
            if removed_count > 0:
                click.echo(f"Cleared {removed_count} cached compatibility instruction(s)")
            else:
                click.echo("Cache was already empty")
            return

    # Load configuration
    cfg = load_config(config)

    # Override config with CLI options
    if directories:
        cfg.scan_directories = list(directories)
    if no_cache:
        cfg.cache_enabled = False

    # Initialize analyzer and reporter
    analyzer = NuShellAnalyzer(cfg, disable_progress=no_progress)
    reporter = Reporter(verbose=verbose)

    try:
        # Run analysis
        results = analyzer.analyze_scripts(target_version=version)

        # Generate report
        reporter.generate_report(results)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


if __name__ == "__main__":
    cli()
