"""Operator CLI: migrations, accounts, projects, retention, the demo data and the OpenAPI document.

Every command works without a terminal, so each also runs as a one-off ECS task
(`make aws-cli ARGS="user create --email ... --password ..."`).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer

from tokenprofiler import __version__
from tokenprofiler.core.config import get_settings
from tokenprofiler.core.logging import configure_logging

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Euron TokenProfiler operator commands.",
)
user_app = typer.Typer(no_args_is_help=True, help="People and roles.")
demo_app = typer.Typer(no_args_is_help=True, help="Demo data.")
app.add_typer(user_app, name="user")
app.add_typer(demo_app, name="demo")


def _setup() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, "console")


@app.command()
def version() -> None:
    """Print the version."""
    typer.echo(__version__)


@app.command()
def migrate(
    revision: Annotated[str, typer.Option(help="Target revision.")] = "head",
) -> None:
    """Apply database migrations (safe to run from several processes at once)."""
    from tokenprofiler.db.migrate import migrate as run

    _setup()
    asyncio.run(run(get_settings(), revision))
    typer.echo(f"database is at {revision}")


@user_app.command("create")
def user_create(
    email: Annotated[str, typer.Option(help="Sign-in email.")],
    name: Annotated[str, typer.Option(help="Display name.")],
    role: Annotated[str, typer.Option(help="admin, member or viewer.")] = "member",
    password: Annotated[
        str | None, typer.Option(help="Initial password; generated when omitted.")
    ] = None,
) -> None:
    """Create a person (the first administrator, or any later account)."""
    from tokenprofiler.services.users import create_user_cli

    _setup()
    created, secret = asyncio.run(
        create_user_cli(get_settings(), email=email, name=name, role=role, password=password)
    )
    typer.echo(f"created {created.role} {created.email}")
    if password is None:
        typer.echo(f"temporary password: {secret}")


@demo_app.command("seed")
def demo_seed(
    force: Annotated[bool, typer.Option(help="Seed again even if the demo people exist.")] = False,
) -> None:
    """Seed people, a project, prompts, budgets and two weeks of traces."""
    from tokenprofiler.demo.seed import seed

    _setup()
    report = asyncio.run(seed(get_settings(), force=force))
    typer.echo(report)


@app.command()
def openapi(
    out: Annotated[Path | None, typer.Option(help="Write to a file instead of stdout.")] = None,
) -> None:
    """Export the OpenAPI document."""
    from tokenprofiler.core.config import Settings
    from tokenprofiler.main import create_app

    document = create_app(Settings()).openapi()
    text = json.dumps(document, indent=2, sort_keys=False) + "\n"
    if out is None:
        typer.echo(text, nl=False)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    typer.echo(f"wrote {out}")


@app.command()
def retention() -> None:
    """Run one retention pass now (the worker does this on a schedule)."""
    from tokenprofiler.services.container import build_container
    from tokenprofiler.services.retention import run_retention

    async def run() -> dict[str, int]:
        container = await build_container(get_settings())
        try:
            return await run_retention(container)
        finally:
            await container.close()

    _setup()
    for slug, removed in asyncio.run(run()).items():
        typer.echo(f"{slug}: removed {removed} trace(s)")


if __name__ == "__main__":
    app()
