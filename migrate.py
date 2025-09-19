#!/usr/bin/env python3
"""
Database migration script - Project root level
Usage:
  python migrate.py migrate           # Run migrations
  python migrate.py create <message>  # Create migration
  python migrate.py current           # Show current revision
  python migrate.py history           # Show migration history
"""
import asyncio
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from alembic.config import Config
from alembic import command
from app.core.config import get_database_url


def run_migrations():
    """Run database migrations."""
    
    # Create alembic config
    alembic_cfg = Config(str(project_root / "alembic.ini"))
    
    # Override database URL
    alembic_cfg.set_main_option("sqlalchemy.url", get_database_url())
    
    try:
        print("🔄 Running database migrations...")
        
        # Run migrations to latest
        command.upgrade(alembic_cfg, "head")
        
        print("✅ Database migrations completed successfully!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)


def create_migration(message: str):
    """Create a new migration."""
    
    alembic_cfg = Config(str(project_root / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", get_database_url())
    
    try:
        print(f"🔄 Creating migration: {message}")
        
        # Create new migration
        command.revision(alembic_cfg, autogenerate=True, message=message)
        
        print("✅ Migration created successfully!")
        
    except Exception as e:
        print(f"❌ Migration creation failed: {e}")
        sys.exit(1)


def check_current_revision():
    """Check current database revision."""
    
    alembic_cfg = Config(str(project_root / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", get_database_url())
    
    try:
        print("🔍 Checking current database revision...")
        
        # Show current revision
        command.current(alembic_cfg)
        
    except Exception as e:
        print(f"❌ Failed to check revision: {e}")
        sys.exit(1)


def show_migration_history():
    """Show migration history."""
    
    alembic_cfg = Config(str(project_root / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", get_database_url())
    
    try:
        print("📋 Migration history:")
        
        # Show history
        command.history(alembic_cfg)
        
    except Exception as e:
        print(f"❌ Failed to show history: {e}")
        sys.exit(1)


def init_migrations():
    """Initialize migration directory (first time setup)."""
    
    migrations_dir = project_root / "migrations"
    
    if migrations_dir.exists():
        print("❌ Migrations directory already exists!")
        return
    
    try:
        print("🔄 Initializing migrations...")
        
        # Initialize alembic
        alembic_cfg = Config(str(project_root / "alembic.ini"))
        command.init(alembic_cfg, str(migrations_dir))
        
        print("✅ Migrations initialized successfully!")
        print("📝 Don't forget to update migrations/env.py with your models!")
        
    except Exception as e:
        print(f"❌ Migration initialization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python migrate.py migrate           # Run migrations")
        print("  python migrate.py create <message>  # Create migration")
        print("  python migrate.py current           # Show current revision")
        print("  python migrate.py history           # Show migration history")
        print("  python migrate.py init              # Initialize migrations (first time)")
        sys.exit(1)
    
    command_name = sys.argv[1].lower()
    
    if command_name == "migrate":
        run_migrations()
    elif command_name == "create":
        if len(sys.argv) < 3:
            print("❌ Please provide a migration message")
            sys.exit(1)
        message = " ".join(sys.argv[2:])
        create_migration(message)
    elif command_name == "current":
        check_current_revision()
    elif command_name == "history":
        show_migration_history()
    elif command_name == "init":
        init_migrations()
    else:
        print(f"❌ Unknown command: {command_name}")
        sys.exit(1)