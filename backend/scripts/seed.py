"""
ParamX Hunter - Database Seed Script
Creates the initial admin user and demo project.

Usage:
    python -m backend.scripts.seed
    python -m backend.scripts.seed --email admin@company.com --password 'SecureP@ss123'
"""

import argparse
import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError

from backend.auth.dependencies import hash_password
from backend.database.models import Project, User, UserRole
from backend.database.session import AsyncSessionLocal


async def create_admin(email: str, username: str, password: str) -> None:
    # NOTE: Schema management is handled by Alembic. Run `alembic upgrade
    # head` before seeding. This script does not create tables itself.
    async with AsyncSessionLocal() as db:
        try:
            existing = await db.execute(select(User).where(User.email == email))
        except ProgrammingError as exc:
            await db.rollback()
            raise SystemExit(
                "Database tables not found. Run `alembic upgrade head` "
                "before seeding the admin user."
            ) from exc

        if existing.scalar_one_or_none():
            print(f"User {email} already exists. Skipping.")
            return

        admin = User(
            id=uuid.uuid4(),
            email=email,
            username=username,
            hashed_password=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
            is_superuser=True,
        )
        db.add(admin)
        await db.flush()

        # Demo project
        project = Project(
            id=uuid.uuid4(),
            name="Demo Project",
            description="Default project created during initial setup",
            owner_id=admin.id,
            settings={"created_by": "seed_script"},
        )
        db.add(project)

        await db.commit()

        print(f"✅ Admin user created: {email}")
        print(f"✅ Demo project created: {project.name} ({project.id})")
        print("\nLogin credentials:")
        print(f"  Email:    {email}")
        print(f"  Password: {password}")
        print("\n⚠️  Change this password immediately after first login.")


def main():
    parser = argparse.ArgumentParser(description="Seed ParamX Hunter database with an admin user")
    parser.add_argument("--email", default="admin@paramxhunter.local")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="ChangeMe123!")
    args = parser.parse_args()

    asyncio.run(create_admin(args.email, args.username, args.password))


if __name__ == "__main__":
    main()
