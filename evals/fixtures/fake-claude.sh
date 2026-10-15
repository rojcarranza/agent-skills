#!/usr/bin/env bash
# Install a stand-in Claude Code CLI for the roj-idea-to-project evals.
#
#   evals/fixtures/fake-claude.sh <fixture-dir> <missing|present|outdated>
#
# Writes <fixture-dir>/bin/claude. Put <fixture-dir>/bin first on PATH for
# the run. Nothing is installed: every call is appended to
# claude-state/calls.log, and plugin install/update/enable switch the state
# to "present" so a re-check after the user's reload passes.
#   missing   no superpowers install
#   present   superpowers@claude-plugins-official 7.0.0, enabled
#   outdated  superpowers@claude-plugins-official 6.4.1, enabled
set -euo pipefail
F=$1; MODE=$2
case "$MODE" in missing|present|outdated) ;; *)
  echo "fake-claude.sh: unknown mode $MODE" >&2; exit 2 ;; esac
mkdir -p "$F/bin" "$F/claude-state"
echo "$MODE" > "$F/claude-state/mode"
: > "$F/claude-state/calls.log"
cat > "$F/bin/claude" <<EOF
#!/usr/bin/env bash
ST="$F/claude-state"
echo "claude \$*" >> "\$ST/calls.log"
sp() { printf '[{"id":"superpowers@claude-plugins-official","version":"%s","scope":"user","enabled":true,"installPath":"/tmp/fake-plugins/superpowers"}]\n' "\$1"; }
case "\$1 \${2:-}" in
  "plugin list")
    case "\$(cat "\$ST/mode")" in
      missing) echo '[]' ;;
      present) sp 7.0.0 ;;
      outdated) sp 6.4.1 ;;
    esac ;;
  "plugin install"|"plugin update"|"plugin enable")
    echo present > "\$ST/mode"
    echo "Successfully installed plugin: \${3:-} (scope: user)" ;;
  "plugin marketplace") echo "Successfully added marketplace" ;;
  "--version ") echo "2.1.300 (Claude Code)" ;;
  *) echo "claude stub: unsupported: \$*" >&2; exit 1 ;;
esac
EOF
chmod +x "$F/bin/claude"
