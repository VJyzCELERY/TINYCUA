---
description: Initializes or updates the .agents structure from a template repository
subtask: true
---

Initialize a new `.agents/` directory or update an existing one with new files from a template.

**Query**: $1 (natural language query — specify the target directory, e.g., "set up .agents in ./my-new-project" or simply "./my-new-project")
**Template Source (Optional)**: $2 (GitHub repo URL or local path, e.g., https://github.com/user/repo)

---

## Behavior

- **If `.agents/` does NOT exist**: Clone or copy the entire template structure (fresh setup).
- **If `.agents/` already exists**: Soft update — copy only files from the template that do NOT yet exist in the project. Existing project-specific files are never overwritten. This lets you pull in new commands, templates, and rules without losing customizations.

---

## Instructions

1. **Determine the target directory**: `$1` (defaults to current directory if empty)

2. **Determine the template source**:
   - If `$2` is provided, use it as a GitHub repo URL
   - If `$2` is empty, default to `https://github.com/VJyzCELERY/MAIN-PROJECT-TEMPLATE`

3. **Clone the template to a temporary location**:
   ```bash
   TMP_DIR=$(mktemp -d)
   git clone --depth 1 "$TEMPLATE_URL" "$TMP_DIR"
   ```

4. **Check if `.agents/` already exists** in the target:

   **If NOT exists (fresh setup)**:
   ```bash
   mkdir -p "$1"
   cp -r "$TMP_DIR/.agents" "$1/.agents"
   ln -sf .agents "$1/.opencode"
   echo "Fresh .agents created from template."
   ```

   **If EXISTS (soft update)**:
   ```bash
   # For each file in the template's .agents/:
   #   - If the file doesn't exist in the project's .agents/, copy it
   #   - If the file already exists, skip it (preserve project customizations)
   cd "$TMP_DIR/.agents"
   find . -type f | while read -r f; do
     target="$1/.agents/$f"
     if [ ! -f "$target" ]; then
       mkdir -p "$(dirname "$target")"
       cp "$f" "$target"
       echo "  + $f (new)"
     else
       echo "  · $f (already exists — skipped)"
     fi
   done
   echo "Soft update complete."
   ```

5. **Clean up**: Remove the temporary clone:
   ```bash
   rm -rf "$TMP_DIR"
   ```

6. **Report**: List what was added (new files) vs skipped (existing files).

---

## Important

- Existing project-specific files in `.agents/` are NEVER overwritten — only new files from the template are added
- To force a full refresh, delete `.agents/` first, then run setup-project again
- The `.opencode` symlink is created if it doesn't exist; if it exists and points elsewhere, it's updated
- Template source defaults to `MAIN-PROJECT-TEMPLATE` on GitHub
