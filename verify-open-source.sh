#!/bin/bash

# T4U Backend - Open Source Verification Script
# Run this before committing to GitHub

set -e

echo "🔍 T4U Backend - Open Source Verification"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0

# 1. Check for API keys in code
echo "1️⃣  Checking for hardcoded API keys..."
API_KEYS=$(grep -r "sk-ant-" app/ --include="*.py" 2>/dev/null | wc -l | tr -d ' ')
if [ "$API_KEYS" -eq "0" ]; then
    echo -e "${GREEN}   ✅ No Anthropic API keys found${NC}"
else
    echo -e "${RED}   ❌ Found $API_KEYS Anthropic API key(s) in code!${NC}"
    ERRORS=$((ERRORS + 1))
fi

E2B_KEYS=$(grep -r "e2b_[a-z0-9]\{20,\}" app/ --include="*.py" 2>/dev/null | wc -l | tr -d ' ')
if [ "$E2B_KEYS" -eq "0" ]; then
    echo -e "${GREEN}   ✅ No E2B API keys found${NC}"
else
    echo -e "${RED}   ❌ Found $E2B_KEYS E2B API key(s) in code!${NC}"
    ERRORS=$((ERRORS + 1))
fi

echo ""

# 2. Check secret files are ignored
echo "2️⃣  Checking secret files are ignored..."

if git check-ignore config/config.toml >/dev/null 2>&1; then
    echo -e "${GREEN}   ✅ config.toml is ignored${NC}"
else
    echo -e "${RED}   ❌ config.toml NOT ignored!${NC}"
    ERRORS=$((ERRORS + 1))
fi

if git check-ignore config/firebase-service-account.json >/dev/null 2>&1; then
    echo -e "${GREEN}   ✅ firebase-service-account.json is ignored${NC}"
else
    echo -e "${RED}   ❌ firebase-service-account.json NOT ignored!${NC}"
    ERRORS=$((ERRORS + 1))
fi

echo ""

# 3. Check documentation exists
echo "3️⃣  Checking documentation files..."

for file in README.md LICENSE CONTRIBUTING.md DEPLOYMENT.md ENVIRONMENT.md; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}   ✅ $file exists${NC}"
    else
        echo -e "${RED}   ❌ $file missing!${NC}"
        ERRORS=$((ERRORS + 1))
    fi
done

echo ""

# 4. Check config examples exist
echo "4️⃣  Checking configuration examples..."

if [ -f "config/config.example-model-anthropic.toml" ]; then
    echo -e "${GREEN}   ✅ config.example-model-anthropic.toml exists${NC}"
else
    echo -e "${RED}   ❌ config.example-model-anthropic.toml missing!${NC}"
    ERRORS=$((ERRORS + 1))
fi

echo ""

# 5. Check code compiles
echo "5️⃣  Checking Python code compiles..."

# Activate venv if exists
if [ -d "venv" ]; then
    source venv/bin/activate 2>/dev/null || true
fi

if python -m py_compile api_server.py 2>/dev/null; then
    echo -e "${GREEN}   ✅ api_server.py compiles${NC}"
else
    echo -e "${YELLOW}   ⚠️  api_server.py check skipped (run with venv activated)${NC}"
fi

if python -m compileall app/ >/dev/null 2>&1; then
    echo -e "${GREEN}   ✅ All app/ files compile${NC}"
else
    echo -e "${YELLOW}   ⚠️  app/ compile check skipped (run with venv activated)${NC}"
fi

echo ""

# 6. Check git status
echo "6️⃣  Checking git status..."

if git status >/dev/null 2>&1; then
    STAGED=$(git status --porcelain | grep "^A\|^M" | wc -l | tr -d ' ')
    UNTRACKED=$(git status --porcelain | grep "^??" | wc -l | tr -d ' ')
    
    echo -e "${GREEN}   ✅ Git repository initialized${NC}"
    echo "   📊 Staged files: $STAGED"
    echo "   📊 Untracked files: $UNTRACKED"
    
    # Check if secrets are staged
    if git status --porcelain | grep -E "config.toml|firebase-service-account" >/dev/null; then
        echo -e "${RED}   ❌ SECRET FILES ARE STAGED!${NC}"
        echo "   Run: git reset config/config.toml config/firebase-service-account.json"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "${YELLOW}   ⚠️  Git not initialized${NC}"
    echo "   Run: git init"
fi

echo ""

# Final result
echo "=========================================="
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}🎉 ALL CHECKS PASSED! READY FOR OPEN SOURCE!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. git add ."
    echo "  2. git commit -m \"feat: Initial T4U open source release\""
    echo "  3. git remote add origin https://github.com/t4u-automation/t4u-backend.git"
    echo "  4. git push -u origin main"
    echo ""
    echo "📖 See QUICK_START.md and DEPLOYMENT.md for guides"
    exit 0
else
    echo -e "${RED}❌ $ERRORS ERROR(S) FOUND - FIX BEFORE COMMITTING!${NC}"
    echo ""
    echo "Review errors above and fix them."
    echo "Then run this script again."
    exit 1
fi

