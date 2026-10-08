#!/usr/bin/env bash
# Install a stand-in GitHub CLI for the roj-review-pr-comment evals.
#
#   evals/fixtures/fake-gh.sh <fixture-dir> <normal|reviewed|noauth>
#
# Writes <fixture-dir>/bin/gh, which serves PR #123 of acme/ingest from the
# local repo built by build.sh. Put <fixture-dir>/bin first on PATH for the
# run. Nothing reaches GitHub: every call is appended to gh-state/calls.log
# and each review POST is saved to gh-state/posted-<n>.json for grading.
#   normal    no earlier review exists
#   reviewed  an earlier review already carries this head SHA's marker
#   noauth    every command fails as if `gh auth login` was never run
set -euo pipefail
F=$1; MODE=$2
mkdir -p "$F/bin" "$F/gh-state"
SHA=$(git -C "$F/repo" rev-parse HEAD)
git -C "$F/repo" diff -U3 origin/main...HEAD > "$F/gh-state/pr.diff"
echo "$MODE" > "$F/gh-state/mode"
echo "$SHA" > "$F/gh-state/sha"
if [ "$MODE" = reviewed ]; then
  printf '**Automated review** — earlier run\n\n<!-- review-pr-comment:%s -->\n' "$SHA" > "$F/gh-state/existing-review-bodies"
else
  : > "$F/gh-state/existing-review-bodies"
fi
cat > "$F/bin/gh" <<EOF
#!/usr/bin/env bash
ST="$F/gh-state"
echo "gh \$*" >> "\$ST/calls.log"
if [ "\$(cat "\$ST/mode")" = noauth ]; then
  echo "To get started with GitHub CLI, please run:  gh auth login" >&2; exit 4
fi
SHA=\$(cat "\$ST/sha")
case "\$1 \$2" in
  "pr view")
    printf '{"number":123,"url":"https://github.com/acme/ingest/pull/123","baseRefName":"main","headRefOid":"%s","isDraft":false,"title":"Retry uploads on transient failures","body":"Uploads fail during the ingest API nightly restart; retry with backoff.","headRepositoryOwner":{"login":"acme"},"headRepository":{"name":"ingest"}}\n' "\$SHA" ;;
  "pr diff") cat "\$ST/pr.diff" ;;
  "api repos/acme/ingest/pulls/123/reviews")
    if printf '%s ' "\$@" | grep -q -- 'POST'; then
      n=\$(ls "\$ST" | grep -c '^posted-' || true)
      cat > "\$ST/posted-\$((n+1)).json"
      echo '{"id":9001,"html_url":"https://github.com/acme/ingest/pull/123#pullrequestreview-9001"}'
    else
      cat "\$ST/existing-review-bodies"
    fi ;;
  *) echo "gh stub: unsupported: \$*" >&2; exit 1 ;;
esac
EOF
chmod +x "$F/bin/gh"
