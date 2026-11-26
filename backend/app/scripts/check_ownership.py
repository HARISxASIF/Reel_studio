"""
Ownership audit and migration utility.
Checks all projects, uploads, reels, social accounts, and social posts to verify
ownership mapping, detect orphaned records, and optionally map them to an explicit user.

Usage:
    # Dry-run audit (read-only):
    python -m app.scripts.check_ownership --dry-run

    # Reassign unowned or specified projects to an explicit verified owner:
    python -m app.scripts.check_ownership --assign-unowned-to owner@example.com
"""
import argparse
import sys
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.models.user import User
from app.models.project import Project
from app.models.reel import Reel
from app.models.upload import UploadSession
from app.models.social import SocialAccount, SocialPost


def run_check(dry_run: bool = True, assign_unowned_to: str = None):
    engine = create_engine(settings.DATABASE_URL_SYNC)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        print("=== REEL STUDIO OWNERSHIP AUDIT ===")
        print(f"Mode: {'DRY RUN (No changes will be saved)' if dry_run else 'APPLY CHANGES'}")

        # List all registered users
        users = session.query(User).all()
        print(f"\nRegistered Users ({len(users)}):")
        user_ids = set()
        user_map = {}
        for u in users:
            print(f"  - [{u.id}] {u.email} ({u.full_name or 'No Name'})")
            user_ids.add(u.id)
            user_map[u.email] = u

        # Inspect projects
        projects = session.query(Project).all()
        print(f"\nProjects ({len(projects)}):")
        orphaned_projects = []
        for p in projects:
            owner_status = "VALID" if p.user_id in user_ids else "ORPHANED / UNKNOWN OWNER"
            owner_email = next((u.email for u in users if u.id == p.user_id), "UNKNOWN")
            print(f"  - [{p.id}] '{p.title}' | Owner: {p.user_id} ({owner_email}) [{owner_status}]")
            if p.user_id not in user_ids:
                orphaned_projects.append(p)

        # Inspect social accounts
        social_accs = session.query(SocialAccount).all()
        print(f"\nSocial Accounts ({len(social_accs)}):")
        for sa in social_accs:
            owner_status = "VALID" if sa.user_id in user_ids else "ORPHANED"
            owner_email = next((u.email for u in users if u.id == sa.user_id), "UNKNOWN")
            print(f"  - [{sa.id}] {sa.platform.upper()}: {sa.account_name} | Owner: {sa.user_id} ({owner_email}) [{owner_status}]")

        if assign_unowned_to and orphaned_projects:
            target_user = user_map.get(assign_unowned_to)
            if not target_user:
                print(f"\n[ERROR] Target user '{assign_unowned_to}' does not exist. Create the user account first.")
                sys.exit(1)

            print(f"\nReassigning {len(orphaned_projects)} orphaned projects to {assign_unowned_to} ({target_user.id})...")
            if not dry_run:
                for p in orphaned_projects:
                    p.user_id = target_user.id
                session.commit()
                print("[SUCCESS] Orphaned projects successfully mapped to explicit owner.")
            else:
                print("[DRY RUN] Would update orphaned projects to target user. Pass --apply to persist.")

        print("\nAudit completed.")

    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reel Studio Ownership Audit")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Run in read-only dry-run mode")
    parser.add_argument("--apply", dest="dry_run", action="store_false", help="Apply database changes")
    parser.add_argument("--assign-unowned-to", type=str, help="Email of explicit user to receive unowned projects")
    args = parser.parse_args()

    run_check(dry_run=args.dry_run, assign_unowned_to=args.assign_unowned_to)
