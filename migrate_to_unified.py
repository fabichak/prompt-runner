#!/usr/bin/env python3
"""
Migration script to move from old architecture to unified orchestrator
This script helps transition the codebase and optionally removes obsolete files
"""

import os
import shutil
from pathlib import Path
import argparse


def parse_args():
    parser = argparse.ArgumentParser(description="Migrate to unified orchestrator architecture")
    parser.add_argument("--backup", action="store_true", help="Backup old files before deletion")
    parser.add_argument("--delete", action="store_true", help="Actually delete obsolete files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without doing it")
    return parser.parse_args()


def main():
    args = parse_args()

    # Files to remove (obsolete)
    obsolete_files = [
        "utils/job_planner.py",
        "services/job_orchestrator.py",
        "services/i2i_orchestrator.py",
        "services/image_scanner.py",
        "services/image_tracker.py",
        "services/workflow_manager.py",  # Replaced by services/workflows/v2v_workflow.py
        "services/i2i_workflow_manager.py",  # Replaced by services/workflows/i2i_workflow.py
    ]

    # Files to rename/move
    file_moves = {
        "main.py": "main_old.py",  # Backup old main
        "main_new.py": "main.py",  # New main becomes the main
    }

    print("🔄 Migration to Unified Orchestrator Architecture")
    print("=" * 60)

    # Handle obsolete files
    print("\n📝 Obsolete files to remove:")
    for file_path in obsolete_files:
        path = Path(file_path)
        if path.exists():
            print(f"  ❌ {file_path}")
            if args.backup and not args.dry_run:
                backup_path = path.with_suffix(path.suffix + ".backup")
                shutil.copy2(path, backup_path)
                print(f"     → Backed up to {backup_path}")

            if args.delete and not args.dry_run:
                path.unlink()
                print(f"     → Deleted")
        else:
            print(f"  ⏭️  {file_path} (already removed)")

    # Handle file moves
    print("\n📝 Files to rename:")
    for old_name, new_name in file_moves.items():
        old_path = Path(old_name)
        new_path = Path(new_name)

        if old_path.exists():
            print(f"  📦 {old_name} → {new_name}")
            if not args.dry_run:
                if new_path.exists() and args.backup:
                    backup_path = new_path.with_suffix(new_path.suffix + ".backup")
                    shutil.copy2(new_path, backup_path)
                    print(f"     → Backed up existing {new_name} to {backup_path}")

                if old_name != "main_new.py" or not new_path.exists():
                    shutil.move(str(old_path), str(new_path))
                    print(f"     → Moved")
        else:
            print(f"  ⏭️  {old_name} (not found)")

    # Print summary of new architecture
    print("\n✨ New Architecture Summary:")
    print("  📁 models/")
    print("     - base_job.py (common interface)")
    print("     - v2v_job.py (video-to-video)")
    print("     - i2i_job.py (image-to-image)")
    print("  📁 services/")
    print("     - unified_orchestrator.py (single orchestrator)")
    print("     - mode_registry.py (mode registration)")
    print("     📁 workflows/")
    print("        - base_workflow.py (common interface)")
    print("        - v2v_workflow.py (v2v workflow manager)")
    print("        - i2i_workflow.py (i2i workflow manager)")

    print("\n🎯 Benefits of new architecture:")
    print("  ✅ Single orchestrator for all modes")
    print("  ✅ 1:1:1 mapping (input → job → output)")
    print("  ✅ API-driven (no file scanning)")
    print("  ✅ Stateless (API handles state)")
    print("  ✅ Easy to add new modes")

    if args.dry_run:
        print("\n⚠️  DRY RUN - No changes were made")
        print("Run without --dry-run to apply changes")
    elif not args.delete:
        print("\n⚠️  Files marked for deletion were not removed")
        print("Run with --delete to remove obsolete files")
    else:
        print("\n✅ Migration complete!")

    # Check for any imports that need updating
    print("\n📝 Remember to update imports in any custom scripts!")
    print("  Old: from services.job_orchestrator import JobOrchestrator")
    print("  New: from services.unified_orchestrator import UnifiedOrchestrator")
    print("\n  Old: from utils.job_planner import JobPlanner")
    print("  New: (No longer needed - removed)")


if __name__ == "__main__":
    main()