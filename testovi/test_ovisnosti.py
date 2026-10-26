import re
import tomllib

from web.postavke import KORIJEN


def _paketi(skupina: str) -> set[str]:
    with (KORIJEN / "pyproject.toml").open("rb") as datoteka:
        ovisnosti = tomllib.load(datoteka)["project"]["optional-dependencies"][skupina]
    return {re.split(r"[<>=!~\[ ;]", ovisnost, maxsplit=1)[0].lower() for ovisnost in ovisnosti}


def test_backend_ima_sve_pakete_gradnje():
    """Backend iscrtava stranice modulima iz web/, a server instalira samo .[backend]."""
    assert _paketi("web") - _paketi("backend") == set()
