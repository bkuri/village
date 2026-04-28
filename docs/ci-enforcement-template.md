# CI Enforcement Template

> **Purpose**: Prevent role-boundary violations at the remote (push) layer.
> This is Layer 4 of Village's defence-in-depth model — the outermost
> enforcement ring that catches anything that bypasses the local execution
> engine.

When a Village session completes, the **Builder** pushes changes to a remote.
Without remote enforcement, a compromised or misconfigured agent could push
changes to protected paths (``specs/``, ``.village/``, ``.github/``).  These
templates provide push-time validation based on the pusher's Village role.

Two approaches are provided:

1. **GitHub Actions** — for GitHub-hosted repos
2. **Self-hosted git hook** — for any git server with shell access

---

## 1. GitHub Actions Workflow

Create ``.github/workflows/village-enforce.yml`` in your repository:

```yaml
name: Village Role Enforcement
on: [push]

jobs:
  enforce:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Identify pusher role
        id: role
        run: |
          AUTHOR=$(git log -1 --format='%an <%ae>' ${{ github.sha }})
          echo "author=$AUTHOR" >> "$GITHUB_OUTPUT"

          # Map author to role — adjust patterns to match your Village roles
          case "$AUTHOR" in
            *"Builder"*)
              echo "role=builder" >> "$GITHUB_OUTPUT"
              echo "allowed=src/ tests/ docs/" >> "$GITHUB_OUTPUT"
              ;;
            *"Planner"*)
              echo="role=planner" >> "$GITHUB_OUTPUT"
              echo "allowed=specs/ .village/ GOALS.md" >> "$GITHUB_OUTPUT"
              ;;
            *"Release"*)
              echo "role=release" >> "$GITHUB_OUTPUT"
              echo "allowed=" >> "$GITHUB_OUTPUT"
              # Release only allowed to create tags — skip path checks
              echo "skip_path_check=true" >> "$GITHUB_OUTPUT"
              ;;
            *)
              echo "role=unknown" >> "$GITHUB_OUTPUT"
              echo "Unknown pusher: $AUTHOR"
              exit 1
              ;;
          esac

      - name: Validate changed paths
        if: steps.role.outputs.skip_path_check != 'true'
        run: |
          ROLE="${{ steps.role.outputs.role }}"
          ALLOWED=(${{ steps.role.outputs.allowed }})

          if [ ${#ALLOWED[@]} -eq 0 ]; then
            echo "No allowed paths configured for role: $ROLE"
            exit 1
          fi

          # Get list of changed files in this push
          if [ "${{ github.event_name }}" = "push" ]; then
            CHANGED=$(git diff --name-only ${{ github.event.before }} ${{ github.sha }})
          else
            CHANGED=$(git diff --name-only origin/${{ github.base_ref }}...HEAD)
          fi

          for file in $CHANGED; do
            MATCHED=false
            for pattern in "${ALLOWED[@]}"; do
              if [[ "$file" == $pattern* ]]; then
                MATCHED=true
                break
              fi
            done
            if [ "$MATCHED" = false ]; then
              echo "ERROR: '$file' is not in $ROLE's allowed paths: ${ALLOWED[*]}"
              exit 1
            fi
          done

          echo "All changes valid for role: $ROLE"
```

### Role-to-path mapping

| Role | Allowed paths | Description |
|------|---------------|-------------|
| ``Builder`` | ``src/``, ``tests/``, ``docs/`` | Implementation work |
| ``Planner`` | ``specs/``, ``.village/``, ``GOALS.md`` | Specification and goals |
| ``Release`` | (tags only) | Version bumps and releases |

Adjust the patterns in the workflow to match your Village role configuration.

---

## 2. Self-Hosted Git Hook (pre-receive)

For non-GitHub repos or self-hosted git servers, use a
``pre-receive`` hook.  Create ``.githooks/pre-receive`` in your repository
(or deploy it server-side):

```bash
#!/bin/bash
# pre-receive hook — reject pushes that violate role-based path restrictions.
#
# This hook runs on the git server for every push.  It checks each
# pushed commit's author against the allowed path map.
#
# Deploy: copy to <repo.git>/hooks/pre-receive and make executable.

set -euo pipefail

# ── Role-to-path mapping ──────────────────────────────────────────────
# Adjust to match your Village role configuration.
declare -A ALLOWED_PATHS
ALLOWED_PATHS["Builder"]="src/ tests/ docs/"
ALLOWED_PATHS["Planner"]="specs/ .village/ GOALS.md"
ALLOWED_PATHS["Release"]=""  # tags only

# Read pushed refs from stdin
while read -r oldrev newrev refname; do
    # Skip tag pushes — allow all tags
    if [[ "$refname" = refs/tags/* ]]; then
        continue
    fi

    # Determine the range of commits being pushed
    if [[ "$oldrev" =~ ^0+$ ]]; then
        # New branch — check all commits from root
        range="$newrev"
    else
        range="$oldrev..$newrev"
    fi

    # Get the author of the tip commit
    author=$(git log -1 --format='%an' "$newrev")

    # Look up the role
    role=""
    allowed=""
    for r in "${!ALLOWED_PATHS[@]}"; do
        if [[ "$author" == *"$r"* ]]; then
            role="$r"
            allowed="${ALLOWED_PATHS[$r]}"
            break
        fi
    done

    if [[ -z "$role" ]]; then
        echo "ERROR: Unknown pusher '$author'. Rejecting push to $refname."
        exit 1
    fi

    echo "Role '$role' pushing to $refname"

    # Release role: only tags are allowed — this ref is not a tag
    if [[ "$role" == "Release" ]]; then
        echo "ERROR: Release role can only push tags, not $refname"
        exit 1
    fi

    # Check all changed files in the push range
    while IFS= read -r file; do
        [[ -z "$file" ]] && continue

        matched=false
        IFS=' ' read -ra patterns <<< "$allowed"
        for pattern in "${patterns[@]}"; do
            if [[ "$file" == "$pattern"* ]]; then
                matched=true
                break
            fi
        done

        if [[ "$matched" == false ]]; then
            echo "ERROR: '$file' is not in '$role' allowed paths: $allowed"
            exit 1
        fi
    done < <(git diff --name-only "$range")
done

exit 0
```

### Deployment

For a bare repository on your git server:

```bash
cp .githooks/pre-receive /path/to/repo.git/hooks/pre-receive
chmod +x /path/to/repo.git/hooks/pre-receive
```

For Gitea / GitLab / self-managed git servers, place the hook in the
repository's ``hooks/`` directory.

---

## 3. Role-Based Deploy Keys Configuration

For defence in depth, each Village role should use a dedicated deploy key
with minimal permissions:

### GitHub deploy keys

| Role | Repository access | Branch restriction |
|------|------------------|--------------------|
| Builder | Write | ``main``, ``feature/*`` |
| Planner | Write | ``main``, ``specs/*`` |
| Release | Write | ``main`` (tags only) |

```bash
# Generate a key pair per role
ssh-keygen -t ed25519 -C "village-builder" -f ~/.ssh/village_builder_ed25519
ssh-keygen -t ed25519 -C "village-planner" -f ~/.ssh/village_planner_ed25519
ssh-keygen -t ed25519 -C "village-release" -f ~/.ssh/village_release_ed25519

# Add to GitHub via:
#   Settings → Deploy keys → Add deploy key
# Enable "Allow write access" for Builder and Release roles.
```

### Git identity configuration

Each role's worktree should have its git identity set to match the role
name so that the CI/hook can map pusher → role:

```bash
# In the Builder's worktree
git config user.name "Village Builder"
git config user.email "builder@village.local"

# In the Planner's worktree
git config user.name "Village Planner"
git config user.email "planner@village.local"

# In the Release worktree
git config user.name "Village Release"
git config user.email "release@village.local"
```

---

## Verification

After deploying the enforcement workflow or hook, verify it works:

```bash
# Test: Builder pushes to specs/ should fail
git checkout -b test-enforce
echo "change" >> specs/test.md
git add specs/test.md
git commit -m "test: builder touching specs"
git push origin test-enforce
# Expected: rejected — 'specs/test.md' not in Builder's allowed paths

# Test: Builder pushes to src/ should succeed
echo "change" >> src/main.py
git add src/main.py
git commit -m "test: builder touching src"
git push origin test-enforce
# Expected: accepted

# Test: Release pushes a branch (not a tag) should fail
git config user.name "Village Release"
git commit --amend --author="Village Release <release@village.local>" --no-edit
git push origin test-enforce --force
# Expected: rejected — Release role can only push tags
```

---

## Notes

- The GitHub Actions workflow requires **``fetch-depth: 0``** so that
  ``git diff`` can compare against the previous commit.
- The pre-receive hook runs **before** the push is accepted — rejected
  pushes are never visible to other clones.
- Both approaches match author **name** (not email) for role mapping.
  Adjust the ``case`` / ``if`` patterns if your role naming convention
  differs.
- For workflows that run on pull requests, use ``pull_request`` trigger
  instead of ``push`` and adjust the ``CHANGED`` file detection
  accordingly.
