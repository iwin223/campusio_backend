#!/usr/bin/env python3
"""
Migration management script for School ERP
"""
import subprocess
import sys
import os

def run_command(command):
    """Run a shell command and return the result"""
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {command}")
        print(f"Error output: {e.stderr}")
        return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python migrate.py <command>")
        print("Commands:")
        print("  create <message>  - Create a new migration")
        print("  migrate           - Run all pending migrations")
        print("  status            - Show current migration status")
        print("  rollback          - Rollback last migration")
        return

    command = sys.argv[1]

    if command == "create":
        if len(sys.argv) < 3:
            print("Usage: python migrate.py create <message>")
            return
        message = " ".join(sys.argv[2:])
        print(f"Creating migration: {message}")
        run_command(f"alembic revision -m \"{message}\"")

    elif command == "migrate":
        print("Running migrations...")
        run_command("alembic upgrade head")

    elif command == "status":
        print("Migration status:")
        run_command("alembic current")

    elif command == "rollback":
        print("Rolling back last migration...")
        run_command("alembic downgrade -1")

    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()