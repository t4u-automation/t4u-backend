#!/usr/bin/env python3
"""
Cleanup script to delete all running E2B sandboxes
Use this to clean up sandboxes left running due to errors or interruptions
"""

from e2b import Sandbox
from app.config import config


def cleanup_all_sandboxes():
    """Delete all running E2B sandboxes"""
    try:
        # Check if E2B is configured
        if not config.e2b or not config.e2b.e2b_api_key:
            print("❌ E2B not configured. Please set e2b_api_key in config.toml")
            return

        api_key = config.e2b.e2b_api_key
        
        print("=" * 70)
        print("🧹 E2B Sandbox Cleanup")
        print("=" * 70)
        print()
        
        # List all sandboxes
        print("📋 Fetching list of running sandboxes...")
        
        # Use synchronous version from e2b
        from e2b import Sandbox
        
        # Get the paginator
        paginator = Sandbox.list(api_key=api_key)
        
        # Collect all sandboxes from all pages
        sandboxes = []
        while True:
            # Get items from current page
            items = paginator.next_items()
            if items:
                sandboxes.extend(items)
            
            # Check if there are more pages (has_next is a property, not a method)
            if not paginator.has_next:
                break
        
        if not sandboxes:
            print("✅ No running sandboxes found. All clean!")
            return
        
        print(f"Found {len(sandboxes)} running sandbox(es):")
        print()
        
        for i, sandbox_info in enumerate(sandboxes, 1):
            sandbox_id = sandbox_info.sandbox_id
            template_id = getattr(sandbox_info, 'template_id', 'unknown')
            started_at = getattr(sandbox_info, 'started_at', 'unknown')
            
            print(f"  [{i}] Sandbox ID: {sandbox_id}")
            print(f"      Template: {template_id}")
            print(f"      Started: {started_at}")
            print()
        
        # Ask for confirmation
        response = input(f"🗑️  Delete all {len(sandboxes)} sandbox(es)? (y/N): ").strip().lower()
        
        if response != 'y':
            print("❌ Cancelled. No sandboxes deleted.")
            return
        
        print()
        print("🗑️  Deleting sandboxes...")
        print()
        
        # Delete each sandbox
        deleted_count = 0
        failed_count = 0
        
        for i, sandbox_info in enumerate(sandboxes, 1):
            sandbox_id = sandbox_info.sandbox_id
            try:
                print(f"  [{i}/{len(sandboxes)}] Deleting {sandbox_id}...", end=" ", flush=True)
                Sandbox.kill(sandbox_id, api_key=api_key)
                print("✅ Deleted")
                deleted_count += 1
            except Exception as e:
                print(f"❌ Failed: {e}")
                failed_count += 1
        
        print()
        print("=" * 70)
        print(f"✅ Cleanup complete!")
        print(f"   Deleted: {deleted_count}")
        if failed_count > 0:
            print(f"   Failed: {failed_count}")
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    cleanup_all_sandboxes()

