import argparse
import asyncio
import getpass
import sys

from cronbox.config import Settings
from cronbox.models.auth import User, UserRole, hash_password
from cronbox.models.database import Base, get_engine, get_session_factory, init_db

from sqlalchemy import select


async def _create_user(args):
    settings = Settings()
    await init_db(settings.db_path)

    # Import auth models to register tables
    import cronbox.models.auth  # noqa: F401

    engine = get_engine(settings.db_path)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    password = args.password
    if not password:
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match", file=sys.stderr)
            sys.exit(1)

    session_factory = get_session_factory(settings.db_path)
    async with session_factory() as session:
        result = await session.execute(
            select(User).where(
                (User.username == args.username) | (User.email == args.email)
            )
        )
        if result.scalar_one_or_none():
            print(f"Error: User '{args.username}' or email '{args.email}' already exists", file=sys.stderr)
            sys.exit(1)

        user = User(
            username=args.username,
            email=args.email,
            password_hash=hash_password(password),
            role=UserRole(args.role),
        )
        session.add(user)
        await session.commit()
        print(f"Created user '{args.username}' with role '{args.role}'")


def main():
    parser = argparse.ArgumentParser(prog="cronbox")
    subparsers = parser.add_subparsers(dest="command")

    # create-user
    create_user_parser = subparsers.add_parser("create-user", help="Create a new user")
    create_user_parser.add_argument("--username", required=True)
    create_user_parser.add_argument("--email", required=True)
    create_user_parser.add_argument("--role", default="viewer", choices=["admin", "operator", "viewer"])
    create_user_parser.add_argument("--password", default=None, help="Password (prompted if not provided)")

    # serve
    serve_parser = subparsers.add_parser("serve", help="Run the cronbox server")
    serve_parser.add_argument("--host", default=None)
    serve_parser.add_argument("--port", type=int, default=None)

    args = parser.parse_args()

    if args.command == "create-user":
        asyncio.run(_create_user(args))
    elif args.command == "serve":
        import uvicorn
        from cronbox.config import Settings as S
        s = S()
        host = args.host or s.api_host
        port = args.port or s.api_port
        uvicorn.run("cronbox.main:app", host=host, port=port)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
