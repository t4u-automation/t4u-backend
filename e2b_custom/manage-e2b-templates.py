#!/usr/bin/env python3
"""
E2B Template Management Script
List and delete unused E2B templates with ease
"""

import subprocess
import sys
import re
from typing import List, Dict

def run_command(cmd: List[str]) -> str:
    """Run a shell command and return output"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running command: {e.stderr}")
        sys.exit(1)

def strip_ansi(text: str) -> str:
    """Remove ANSI color codes from text"""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def list_templates() -> List[Dict]:
    """List all E2B templates"""
    print("📋 Fetching your E2B templates...")
    output = run_command(['e2b', 'template', 'list'])
    
    # Strip ANSI codes
    output = strip_ansi(output)
    
    templates = []
    lines = output.split('\n')
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines and header lines
        if not line or 'Access' in line or 'Template ID' in line or 'Sandbox templates' in line:
            continue
        
        # Extract template ID - it's typically the alphanumeric string after "Private"
        # Pattern: Private <TEMPLATE_ID> <NAME> <CORES> <MEMORY> ...
        parts = line.split()
        
        if len(parts) >= 2 and parts[0].lower() == 'private':
            template_id = parts[1]
            # Template name is everything after ID until we hit numbers (cores)
            # Usually parts[2] onwards until we find a number
            template_name = ""
            for i in range(2, len(parts)):
                if parts[i].isdigit() or parts[i][0].isdigit():
                    break
                template_name += parts[i] + " "
            template_name = template_name.strip()
            
            if template_id:  # Make sure we got a valid template ID
                templates.append({'id': template_id, 'name': template_name or '(no name)', 'raw': line})
    
    return templates

def delete_template(template_id: str) -> bool:
    """Delete a specific template"""
    try:
        print(f"🗑️  Deleting template '{template_id}'...", end='', flush=True)
        # Pipe "yes" to stdin to automatically confirm the deletion
        result = subprocess.run(
            f"echo 'yes' | e2b template delete {template_id}",
            shell=True,
            capture_output=True,
            text=True,
            timeout=30  # 30 second timeout
        )
        
        if result.returncode == 0 or "Deleting" in result.stdout:
            print(f" ✅")
            return True
        else:
            print(f" ❌")
            if result.stderr:
                print(f"   Error: {result.stderr[:200]}")
            return False
    except subprocess.TimeoutExpired:
        print(f" ❌ (TIMEOUT)")
        return False
    except Exception as e:
        print(f" ❌ (Exception: {str(e)[:100]})")
        return False

def main():
    print("╔════════════════════════════════════════════╗")
    print("║  E2B Template Management Tool              ║")
    print("╚════════════════════════════════════════════╝")
    print("")
    
    templates = list_templates()
    
    if not templates:
        print("No templates found.")
        sys.exit(0)
    
    print(f"\n📊 Found {len(templates)} template(s):\n")
    
    for i, template in enumerate(templates, 1):
        print(f"  {i}. {template['id']}  ({template.get('name', 'unnamed')})")
    
    print("\n════════════════════════════════════════════")
    print("\nOptions:")
    print("  1. Delete a specific template by ID")
    print("  2. Delete multiple templates (interactive)")
    print("  3. Exit")
    print("")
    
    choice = input("Enter your choice (1-3): ").strip()
    
    if choice == "1":
        template_id = input("Enter template ID to delete: ").strip()
        if template_id:
            confirm = input(f"⚠️  Delete '{template_id}'? (yes/no): ").strip().lower()
            if confirm == "yes":
                delete_template(template_id)
    
    elif choice == "2":
        to_delete = []
        for template in templates:
            delete = input(f"Delete '{template['id']}' ({template.get('name', 'unnamed')})? (yes/no): ").strip().lower()
            if delete == "yes":
                to_delete.append(template)
        
        if to_delete:
            print(f"\n⚠️  About to delete {len(to_delete)} template(s):")
            for t in to_delete:
                print(f"  - {t['id']}  ({t.get('name', 'unnamed')})")
            
            final_confirm = input("\nProceed with deletion? (yes/no): ").strip().lower()
            if final_confirm == "yes":
                for t in to_delete:
                    delete_template(t['id'])
                print(f"\n✅ Deleted {len(to_delete)} template(s)")
    
    else:
        print("Exiting.")
        sys.exit(0)

if __name__ == "__main__":
    main()
