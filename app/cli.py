"""Operator CLI. Run inside the api container:

    docker compose exec api python -m app.cli create-admin
    docker compose exec api python -m app.cli create-admin --reset-password

`argparse` is the stdlib equivalent of Go's `flag` package (with subcommands).
Passwords are only ever read interactively (`getpass`, no echo) — never from flags,
which would end up in shell history.
"""

import argparse
import getpass
import sys
from collections.abc import Callable, Sequence

from app.core import security
from app.core.errors import AppError
from app.db.session import get_sessionmaker
from app.services import auth_service

Prompt = Callable[[str], str]


def _read_new_password(getpass_fn: Prompt) -> str:
    first = getpass_fn(f"Password (min {security.PASSWORD_MIN_LENGTH} characters): ")
    second = getpass_fn("Repeat password: ")
    if first != second:
        raise AppError("Passwords do not match.", code="PASSWORD_MISMATCH")
    return first


def create_admin(
    *,
    reset_password: bool,
    email: str | None = None,
    input_fn: Prompt | None = None,
    getpass_fn: Prompt | None = None,
    out: Callable[[str], None] = print,
) -> int:
    # Resolved at call time (not as default values) so tests can swap them in.
    input_fn = input_fn or input
    getpass_fn = getpass_fn or getpass.getpass
    with get_sessionmaker()() as db:
        existing = auth_service.user_count(db)

        if reset_password:
            if existing == 0:
                out("No admin user exists yet. Run `create-admin` without --reset-password.")
                return 1
            user = auth_service.reset_password(db, _read_new_password(getpass_fn))
            out(f"Password reset for {user.email}. All refresh tokens were revoked.")
            return 0

        if existing > 0:
            out("An admin user already exists. Use --reset-password to change its password.")
            return 1

        email = email or input_fn("Admin email: ")
        user = auth_service.create_admin(db, email, _read_new_password(getpass_fn))
        out(f"Admin created: {user.email}")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="AEOLUS operator CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_admin = sub.add_parser("create-admin", help="Create the single admin user")
    p_admin.add_argument(
        "--reset-password", action="store_true", help="Set a new password for the existing admin"
    )
    p_admin.add_argument("--email", help="Admin email (otherwise prompted)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "create-admin":
            return create_admin(reset_password=args.reset_password, email=args.email)
    except AppError as exc:
        print(f"Error: {exc.message}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\nAborted.", file=sys.stderr)
        return 130
    return 2  # unreachable: argparse rejects unknown commands


if __name__ == "__main__":
    raise SystemExit(main())
