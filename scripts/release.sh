#!/usr/bin/env bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Validate arguments
if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 0.2.0"
    exit 1
fi

VERSION="$1"
TAG="v${VERSION}"

# Validate version format (semver: X.Y.Z or X.Y.Za1, X.Y.Zb1, X.Y.Zrc1)
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+((a|b|rc)[0-9]+)?$ ]]; then
    error "Invalid version format: $VERSION (expected: X.Y.Z or X.Y.Za1/b1/rc1)"
fi

info "Preparing release ${TAG}..."

# Check we're in the repo root
if [[ ! -f "pyproject.toml" ]]; then
    error "Must be run from repository root (pyproject.toml not found)"
fi

# Check for uncommitted changes (ignore untracked files)
if [[ -n "$(git status --porcelain | grep -v '^?? ')" ]]; then
    error "Working directory has staged or unstaged changes. Commit or stash changes first."
fi

# Check tag doesn't exist locally
if git tag -l | grep -q "^${TAG}$"; then
    error "Tag ${TAG} already exists locally"
fi

# Check tag doesn't exist on remote
if git ls-remote --tags origin | grep -q "refs/tags/${TAG}$"; then
    error "Tag ${TAG} already exists on remote"
fi

# Get current version
CURRENT_VERSION=$(grep '^version = ' pyproject.toml | head -1 | sed 's/version = "\(.*\)"/\1/')
info "Current version: ${CURRENT_VERSION}"
info "New version: ${VERSION}"

# Run all checks
info "Running checks (lint, format, typecheck, tests)..."
make check || error "Checks failed. Fix issues before releasing."

# Update version in pyproject.toml
info "Updating version in pyproject.toml..."
sed -i.bak "s/^version = \".*\"/version = \"${VERSION}\"/" pyproject.toml && rm pyproject.toml.bak

# Update version in __init__.py
info "Updating version in src/beancount_zenmoney/__init__.py..."
sed -i.bak "s/^__version__ = \".*\"/__version__ = \"${VERSION}\"/" src/beancount_zenmoney/__init__.py && rm src/beancount_zenmoney/__init__.py.bak

# Verify updates
UPDATED_PYPROJECT=$(grep '^version = ' pyproject.toml | head -1)
UPDATED_INIT=$(grep '^__version__ = ' src/beancount_zenmoney/__init__.py)
info "Updated pyproject.toml: ${UPDATED_PYPROJECT}"
info "Updated __init__.py: ${UPDATED_INIT}"

# Commit version bump
info "Committing version bump..."
git add pyproject.toml src/beancount_zenmoney/__init__.py
git commit -m "Release ${TAG}"

# Create tag
info "Creating tag ${TAG}..."
git tag -a "${TAG}" -m "Release ${TAG}"

# Push to remote
info "Pushing commits and tags to remote..."
git push origin HEAD
git push origin "${TAG}"

info "Release ${TAG} complete!"
echo ""
echo "Next steps:"
echo "  - Monitor the GitHub Actions workflow: https://github.com/MrLokans/beancount-zenmoney/actions"
echo "  - Check PyPI after workflow completes: https://pypi.org/project/beancount-zenmoney/"
