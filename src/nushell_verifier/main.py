#!/usr/bin/env python3

def main():
    """Main entry point for nushell-verifier CLI."""
    from .cli import cli
    cli()

if __name__ == "__main__":
    main()