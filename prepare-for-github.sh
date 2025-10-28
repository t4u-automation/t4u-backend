#!/bin/bash

# T4U Backend - Prepare for GitHub
# Removes secrets from git tracking

echo "🧹 Preparing T4U Backend for GitHub"
echo "===================================="
echo ""

# Remove secrets from git tracking (they're already in .gitignore)
echo "Removing secrets from git tracking..."

if git ls-files | grep -q "config/firebase-service-account.json"; then
    git rm --cached config/firebase-service-account.json
    echo "  ✅ Removed config/firebase-service-account.json from git"
else
    echo "  ✅ config/firebase-service-account.json already not tracked"
fi

if git ls-files | grep -q "config/config.toml"; then
    git rm --cached config/config.toml
    echo "  ✅ Removed config/config.toml from git"
else
    echo "  ✅ config/config.toml already not tracked"
fi

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "Run verification:"
echo "  ./verify-open-source.sh"
echo ""
echo "If verification passes, commit and push:"
echo "  git add ."
echo '  git commit -m "feat: Initial T4U open source release"'
echo "  git remote add origin https://github.com/t4u-automation/t4u-backend.git"
echo "  git push -u origin main"

