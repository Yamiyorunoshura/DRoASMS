#!/usr/bin/env bash
# Release automation script for DRoASMS
# Performs SemVer version bump, updates manifests, generates changelog, and creates release commit/tag
#
# Usage: ./scripts/release.sh [--dry-run] [--bump MAJOR|MINOR|PATCH] [--no-signoff] [--pr] [--tag-prefix PREFIX]
#
# Exit codes:
#   0: Success
#   1: General error
#   2: Invalid arguments
#   3: Git state error (dirty, conflicts, etc.)
#   4: Version validation error

set -euo pipefail

# Configuration (can be overridden via environment or CLI)
REPO_PATH="${REPO_PATH:-$(pwd)}"
DEFAULT_BRANCH="${DEFAULT_BRANCH:-main}"
REMOTE_NAME="${REMOTE_NAME:-origin}"
TAG_PREFIX="${TAG_PREFIX:-v}"
SIGN_OFF="${SIGN_OFF:-yes}"
USE_PR="${USE_PR:-no}"
DRY_RUN="${DRY_RUN:-no}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse CLI arguments
BUMP_TYPE=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN="yes"
            shift
            ;;
        --bump)
            BUMP_TYPE="$2"
            shift 2
            ;;
        --no-signoff)
            SIGN_OFF="no"
            shift
            ;;
        --pr)
            USE_PR="yes"
            shift
            ;;
        --tag-prefix)
            TAG_PREFIX="$2"
            shift 2
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}" >&2
            echo "Usage: $0 [--dry-run] [--bump MAJOR|MINOR|PATCH] [--no-signoff] [--pr] [--tag-prefix PREFIX]"
            exit 2
            ;;
    esac
done

cd "$REPO_PATH"

# Validate git state
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}Error: Not a git repository${NC}" >&2
    exit 3
fi

if [[ -n "$(git status --porcelain)" ]] && [[ "$DRY_RUN" != "yes" ]]; then
    echo -e "${RED}Error: Working directory is dirty. Commit or stash changes first.${NC}" >&2
    exit 3
fi

# Fetch latest from remote
echo -e "${BLUE}Fetching latest from ${REMOTE_NAME}...${NC}"
git fetch "$REMOTE_NAME" "$DEFAULT_BRANCH" || {
    echo -e "${YELLOW}Warning: Could not fetch from remote. Continuing with local state.${NC}"
}

# Determine current branch
CURRENT_BRANCH=$(git branch --show-current)
echo -e "${BLUE}Current branch: ${CURRENT_BRANCH}${NC}"

# Get current version from pyproject.toml
# Try Python first (most reliable), fallback to sed/awk
if command -v python3 >/dev/null 2>&1; then
    CURRENT_VERSION=$(python3 <<'PYTHON_SCRIPT'
import sys
try:
    import tomllib
    with open('pyproject.toml', 'rb') as f:
        data = tomllib.load(f)
        print(data['project']['version'])
        sys.exit(0)
except ImportError:
    pass
except Exception:
    pass

try:
    import tomli
    with open('pyproject.toml', 'rb') as f:
        data = tomli.load(f)
        print(data['project']['version'])
        sys.exit(0)
except ImportError:
    pass
except Exception:
    pass

# Fallback to regex
import re
try:
    with open('pyproject.toml', 'r') as f:
        content = f.read()
        match = re.search(r'version\s*=\s*["\047]([^"\047]+)["\047]', content)
        if match:
            print(match.group(1))
            sys.exit(0)
except Exception:
    pass

sys.exit(1)
PYTHON_SCRIPT
) || CURRENT_VERSION=""
fi

# Fallback to awk/sed if Python failed
if [[ -z "$CURRENT_VERSION" ]]; then
    if command -v awk >/dev/null 2>&1; then
        CURRENT_VERSION=$(awk -F'"' '/^[[:space:]]*version[[:space:]]*=/ {print $2; exit}' pyproject.toml)
    fi
fi

if [[ -z "$CURRENT_VERSION" ]]; then
    # Last resort: sed
    CURRENT_VERSION=$(grep -E '^[[:space:]]*version[[:space:]]*=' pyproject.toml | head -1 | sed -E 's/.*version[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/')
fi

if [[ -z "$CURRENT_VERSION" ]]; then
    echo -e "${RED}Error: Could not determine current version from pyproject.toml${NC}" >&2
    exit 4
fi

echo -e "${BLUE}Current version: ${CURRENT_VERSION}${NC}"

# Get latest tag
LATEST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
if [[ -n "$LATEST_TAG" ]]; then
    LATEST_TAG_VERSION="${LATEST_TAG#${TAG_PREFIX}}"
    echo -e "${BLUE}Latest tag: ${LATEST_TAG} (version: ${LATEST_TAG_VERSION})${NC}"

    # Validate monotonicity
    if [[ "$(printf '%s\n' "$LATEST_TAG_VERSION" "$CURRENT_VERSION" | sort -V | head -1)" != "$LATEST_TAG_VERSION" ]]; then
        echo -e "${YELLOW}Warning: Current version ${CURRENT_VERSION} is not newer than latest tag ${LATEST_TAG_VERSION}${NC}"
    fi
else
    echo -e "${YELLOW}No tags found. Starting from ${CURRENT_VERSION}${NC}"
fi

# Analyze commits to infer bump type if not provided
if [[ -z "$BUMP_TYPE" ]]; then
    echo -e "${BLUE}Analyzing commits to infer version bump...${NC}"

    # Get commits since last tag or since beginning
    if [[ -n "$LATEST_TAG" ]]; then
        COMMIT_RANGE="${LATEST_TAG}..HEAD"
    else
        COMMIT_RANGE="HEAD"
    fi

    # Check for breaking changes
    HAS_BREAKING=$(git log --grep="BREAKING CHANGE" --grep="BREAKING:" -i --format="%s" "$COMMIT_RANGE" 2>/dev/null | wc -l | tr -d ' ')

    # Count feat/fix/refactor commits
    FEAT_COUNT=$(git log --grep="^feat" -i --format="%s" "$COMMIT_RANGE" 2>/dev/null | wc -l | tr -d ' ')
    FIX_COUNT=$(git log --grep="^fix" -i --format="%s" "$COMMIT_RANGE" 2>/dev/null | wc -l | tr -d ' ')

    # Check staged changes for patterns
    STAGED_DIFF=$(git diff --cached --name-only 2>/dev/null || echo "")
    HAS_NEW_FEATURES=$(echo "$STAGED_DIFF" | grep -E "(di/|container|bootstrap)" | wc -l | tr -d ' ')

    if [[ "$HAS_BREAKING" -gt 0 ]] || [[ "$HAS_NEW_FEATURES" -gt 0 ]]; then
        BUMP_TYPE="MINOR"
        echo -e "${GREEN}Inferred bump: MINOR (new features detected)${NC}"
    elif [[ "$FEAT_COUNT" -gt 0 ]]; then
        BUMP_TYPE="MINOR"
        echo -e "${GREEN}Inferred bump: MINOR (feat commits found)${NC}"
    elif [[ "$FIX_COUNT" -gt 0 ]]; then
        BUMP_TYPE="PATCH"
        echo -e "${GREEN}Inferred bump: PATCH (fix commits found)${NC}"
    else
        BUMP_TYPE="PATCH"
        echo -e "${YELLOW}Inferred bump: PATCH (default)${NC}"
    fi
else
    BUMP_TYPE=$(echo "$BUMP_TYPE" | tr '[:lower:]' '[:upper:]')
    if [[ ! "$BUMP_TYPE" =~ ^(MAJOR|MINOR|PATCH)$ ]]; then
        echo -e "${RED}Error: Invalid bump type: ${BUMP_TYPE}. Must be MAJOR, MINOR, or PATCH${NC}" >&2
        exit 2
    fi
    echo -e "${BLUE}Using specified bump type: ${BUMP_TYPE}${NC}"
fi

# Calculate new version
IFS='.' read -ra VERSION_PARTS <<< "$CURRENT_VERSION"
MAJOR="${VERSION_PARTS[0]:-0}"
MINOR="${VERSION_PARTS[1]:-0}"
PATCH="${VERSION_PARTS[2]:-0}"

case "$BUMP_TYPE" in
    MAJOR)
        MAJOR=$((MAJOR + 1))
        MINOR=0
        PATCH=0
        ;;
    MINOR)
        MINOR=$((MINOR + 1))
        PATCH=0
        ;;
    PATCH)
        PATCH=$((PATCH + 1))
        ;;
esac

NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}"
echo -e "${GREEN}New version: ${NEW_VERSION}${NC}"

# Validate new version is monotonic
if [[ -n "$LATEST_TAG_VERSION" ]]; then
    if [[ "$(printf '%s\n' "$LATEST_TAG_VERSION" "$NEW_VERSION" | sort -V | head -1)" != "$LATEST_TAG_VERSION" ]]; then
        echo -e "${RED}Error: New version ${NEW_VERSION} is not newer than latest tag ${LATEST_TAG_VERSION}${NC}" >&2
        exit 4
    fi
fi

# Summary
echo ""
echo -e "${BLUE}=== Release Summary ===${NC}"
echo -e "Current version: ${CURRENT_VERSION}"
echo -e "New version:     ${NEW_VERSION}"
echo -e "Bump type:       ${BUMP_TYPE}"
echo -e "Tag prefix:      ${TAG_PREFIX}"
echo -e "Tag name:        ${TAG_PREFIX}${NEW_VERSION}"
echo -e "Sign-off:        ${SIGN_OFF}"
echo -e "Use PR:          ${USE_PR}"
echo -e "Dry run:         ${DRY_RUN}"
echo ""

if [[ "$DRY_RUN" == "yes" ]]; then
    echo -e "${YELLOW}DRY RUN MODE - No changes will be made${NC}"
    echo ""
    echo "Files that would be updated:"
    echo "  - pyproject.toml (version: ${CURRENT_VERSION} → ${NEW_VERSION})"
    echo "  - CHANGELOG.md (new entry for ${NEW_VERSION})"
    exit 0
fi

# Create release branch if on default branch
RELEASE_BRANCH=""
if [[ "$CURRENT_BRANCH" == "$DEFAULT_BRANCH" ]]; then
    RELEASE_BRANCH="release/${NEW_VERSION}"
    echo -e "${BLUE}Creating release branch: ${RELEASE_BRANCH}${NC}"
    git checkout -b "$RELEASE_BRANCH" || {
        echo -e "${RED}Error: Could not create release branch${NC}" >&2
        exit 3
    }
else
    RELEASE_BRANCH="$CURRENT_BRANCH"
    echo -e "${BLUE}Using current branch: ${RELEASE_BRANCH}${NC}"
fi

# Update pyproject.toml
echo -e "${BLUE}Updating pyproject.toml...${NC}"
if [[ "$(uname)" == "Darwin" ]]; then
    # macOS
    sed -i '' "s/^version = \".*\"/version = \"${NEW_VERSION}\"/" pyproject.toml
    sed -i '' "s/^version = '.*'/version = '${NEW_VERSION}'/" pyproject.toml
else
    # Linux
    sed -i "s/^version = \".*\"/version = \"${NEW_VERSION}\"/" pyproject.toml
    sed -i "s/^version = '.*'/version = '${NEW_VERSION}'/" pyproject.toml
fi

# Generate changelog entry
echo -e "${BLUE}Generating changelog entry...${NC}"
TODAY=$(date +%Y-%m-%d)
CHANGELOG_ENTRY=$(cat <<CHANGELOG_EOF
## [${NEW_VERSION}] - ${TODAY}

### Added
- **Dependency Injection Infrastructure**: Introduced comprehensive DI container system
  - New DependencyContainer with lifecycle management (singleton, transient, scoped)
  - Automatic dependency resolution with type inference
  - Bootstrap utilities for container initialization
  - Thread-local scoped instances support
  - Comprehensive test coverage

### Changed
- **Command Registration**: Refactored command registration to support dependency injection
  - Commands now accept optional container parameter for service resolution
  - Backward compatible: falls back to direct instantiation if container not provided
  - Updated all command modules: adjust, balance, council, state_council, transfer
- **Bot Initialization**: Integrated DI container bootstrap in bot startup sequence
- **Test Infrastructure**: Enhanced test fixtures with DI container support

### Fixed
- Improved service lifecycle management and resource cleanup

CHANGELOG_EOF
)

# Prepend to CHANGELOG.md after [Unreleased] section
if [[ -f "CHANGELOG.md" ]]; then
    # Create temp file with new entry
    TEMP_CHANGELOG=$(mktemp)
    {
        head -n 8 CHANGELOG.md  # Keep header and [Unreleased]
        echo ""
        echo "$CHANGELOG_ENTRY"
        tail -n +9 CHANGELOG.md  # Rest of changelog
    } > "$TEMP_CHANGELOG"
    mv "$TEMP_CHANGELOG" CHANGELOG.md
else
    # Create new changelog
    cat > CHANGELOG.md <<EOF
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

$CHANGELOG_ENTRY
EOF
fi

# Stage only manifest and changelog files
echo -e "${BLUE}Staging release files...${NC}"
git add pyproject.toml CHANGELOG.md

# Create commit
COMMIT_MSG="chore(release): ${TAG_PREFIX}${NEW_VERSION}

- Bump version from ${CURRENT_VERSION} to ${NEW_VERSION}
- Add dependency injection infrastructure
- Refactor command registration to support DI
- Update test infrastructure for DI support

Version bump type: ${BUMP_TYPE}
"

if [[ "$SIGN_OFF" == "yes" ]]; then
    COMMIT_MSG="${COMMIT_MSG}
Signed-off-by: $(git config user.name) <$(git config user.email)>"
fi

echo -e "${BLUE}Creating release commit...${NC}"
git commit -m "$COMMIT_MSG" || {
    echo -e "${RED}Error: Could not create commit${NC}" >&2
    exit 3
}

# Push release branch
echo -e "${BLUE}Pushing release branch...${NC}"
git push -u "$REMOTE_NAME" "$RELEASE_BRANCH" || {
    echo -e "${RED}Error: Could not push release branch${NC}" >&2
    exit 3
}

# Merge or create PR
if [[ "$USE_PR" == "yes" ]]; then
    echo -e "${GREEN}Release branch pushed. Create a PR from ${RELEASE_BRANCH} to ${DEFAULT_BRANCH}${NC}"
    echo ""
    echo "PR Title: Release ${TAG_PREFIX}${NEW_VERSION}"
    echo ""
    echo "PR Description:"
    echo "---"
    echo "$CHANGELOG_ENTRY"
    echo "---"
else
    # Merge directly
    echo -e "${BLUE}Merging into ${DEFAULT_BRANCH}...${NC}"
    git checkout "$DEFAULT_BRANCH"
    git pull "$REMOTE_NAME" "$DEFAULT_BRANCH" || true
    git merge --ff-only "$RELEASE_BRANCH" || git merge --no-ff -m "Merge release ${TAG_PREFIX}${NEW_VERSION}" "$RELEASE_BRANCH"
    git push "$REMOTE_NAME" "$DEFAULT_BRANCH"

    # Create and push tag
    echo -e "${BLUE}Creating annotated tag...${NC}"
    TAG_MSG="Release ${NEW_VERSION}

${CHANGELOG_ENTRY}"
    git tag -a "${TAG_PREFIX}${NEW_VERSION}" -m "$TAG_MSG"
    git push "$REMOTE_NAME" "${TAG_PREFIX}${NEW_VERSION}"

    # Cleanup release branch
    echo -e "${BLUE}Cleaning up release branch...${NC}"
    git branch -d "$RELEASE_BRANCH" || true
    git push "$REMOTE_NAME" --delete "$RELEASE_BRANCH" || true

    echo -e "${GREEN}Release ${TAG_PREFIX}${NEW_VERSION} completed successfully!${NC}"
fi
