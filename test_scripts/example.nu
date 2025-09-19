#!/usr/bin/env nu
# nushell-compatible-with: 0.90.0

# Example NuShell script
echo "Hello from NuShell!"
ls | where type == "file" | length