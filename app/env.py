from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def load_env() -> bool:
    """
    Load environment variables from the project's .env file.

    This repo currently stores the env file at `app/.env`, but many modules were
    calling `load_dotenv()` without a path, which only works when you run the
    app from the same directory as the .env file.
    """

    # app/env.py -> app/
    app_dir = Path(__file__).resolve().parent
    candidates = [
        app_dir / ".env",  # current repo layout
        app_dir.parent / ".env",  # common layout: project-root/.env
    ]

    for p in candidates:
        if p.exists():
            return load_dotenv(dotenv_path=p, override=False)

    # Fall back to default behavior (search current working directory).
    return load_dotenv(override=False)

