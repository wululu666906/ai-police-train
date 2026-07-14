import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_ENV_PATH = Path(__file__).resolve().parent / ".env"


def _drop_unreadable_file_env(name: str) -> None:
    value = os.getenv(name)
    if not value:
        return
    try:
        path = Path(value)
        with path.open("rb") as handle:
            handle.read(1)
    except OSError:
        os.environ.pop(name, None)


def _drop_unreadable_dir_env(name: str) -> None:
    value = os.getenv(name)
    if not value:
        return
    try:
        path = Path(value)
        if not path.is_dir():
            raise OSError
        next(path.iterdir(), None)
    except OSError:
        os.environ.pop(name, None)


def sanitize_ssl_env() -> None:
    for name in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        _drop_unreadable_file_env(name)
    _drop_unreadable_dir_env("SSL_CERT_DIR")


def load_backend_env() -> None:
    sanitize_ssl_env()
    load_dotenv(BACKEND_ENV_PATH, override=False)
