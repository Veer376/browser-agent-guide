#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
source_path="$script_dir/pw.py"
target_path="${1:-$HOME/.local/bin/pw}"
target_dir=$(dirname -- "$target_path")

mkdir -p "$target_dir"

if [ -e "$target_path" ] || [ -L "$target_path" ]; then
  existing=$(readlink "$target_path" 2>/dev/null || true)
  if [ "$existing" = "$source_path" ]; then
    echo "pw is already installed at $target_path"
    exit 0
  fi
  echo "Refusing to replace existing path: $target_path" >&2
  exit 1
fi

ln -s "$source_path" "$target_path"
echo "Installed pw at $target_path"
