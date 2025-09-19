#!/usr/bin/env nu

# nushell-compatible-with: 0.107.0

# This script should be skipped if target version is 0.107.0 or older
echo "This script is already compatible!"
ls | where type == file