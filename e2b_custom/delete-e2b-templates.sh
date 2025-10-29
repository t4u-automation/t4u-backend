#!/bin/bash

# E2B Template Deletion Script
# This script helps you list and delete unused E2B templates

set -e

echo "╔════════════════════════════════════════════╗"
echo "║  E2B Template Management                   ║"
echo "╚════════════════════════════════════════════╝"
echo ""

# List all templates
echo "📋 Fetching your E2B templates..."
echo ""

e2b template list

echo ""
echo "════════════════════════════════════════════"
echo ""
echo "To delete a template, run:"
echo ""
echo "  e2b template delete <TEMPLATE_ID>"
echo ""
echo "Example:"
echo "  e2b template delete 97h12m86c734x32etx23"
echo ""
echo "════════════════════════════════════════════"
echo ""
echo "Or use this interactive delete mode:"
echo ""

read -p "Enter template ID to delete (or press Enter to skip): " template_id

if [ -z "$template_id" ]; then
    echo "❌ No template ID provided. Exiting."
    exit 0
fi

read -p "⚠️  Are you sure you want to delete template '$template_id'? (yes/no): " confirm

if [ "$confirm" = "yes" ]; then
    echo "🗑️  Deleting template '$template_id'..."
    e2b template delete "$template_id"
    echo "✅ Template deleted successfully!"
else
    echo "❌ Deletion cancelled."
    exit 0
fi
