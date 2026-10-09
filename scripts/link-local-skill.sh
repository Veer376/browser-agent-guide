#!/bin/sh
# Create a discoverable ~/.agents/skills/playwright installation while keeping
# all editable files in this project's skills/playwright/ tree.
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo=$(CDPATH= cd -- "$script_dir/.." && pwd)
skill="$repo/skills/playwright"
target="$HOME/.agents/skills/playwright"

[ -f "$skill/SKILL.md" ] || { echo 'Missing project Playwright skill.' >&2; exit 1; }
mkdir -p "$HOME/.agents/skills"

# Compatibility: a prior version of this project may have installed a whole
# directory symlink, which Local System does not discover. Only replace it when
# it points to this exact project's skill folder.
if [ -L "$target" ]; then
  [ "$(readlink "$target")" = "$skill" ] || {
    echo "Refusing to change unrelated symlink: $target" >&2
    exit 1
  }
  unlink "$target"
fi

if [ ! -e "$target" ]; then
  mkdir "$target"
fi
[ -d "$target" ] || { echo "Not a directory: $target" >&2; exit 1; }

for name in SKILL.md scripts references assets agents tests; do
  origin="$skill/$name"
  destination="$target/$name"
  if [ -L "$destination" ]; then
    [ "$(readlink "$destination")" = "$origin" ] || {
      echo "Refusing to replace unrelated symlink: $destination" >&2
      exit 1
    }
    continue
  fi
  if [ -e "$destination" ]; then
    echo "Refusing to replace existing file/directory: $destination" >&2
    exit 1
  fi
  ln -s "$origin" "$destination"
done

printf 'Playwright skill linked: %s → %s\n' "$target" "$skill"
