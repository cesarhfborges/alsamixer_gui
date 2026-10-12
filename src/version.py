"""Versão do app (setuptools-scm / vcs-versioning, a partir das tags do git).

No build, `src/_version.py` é gerado pelo setuptools-scm e embutido no binário.
Em desenvolvimento, sem esse arquivo, a versão é calculada pelo git.
"""


def get_version() -> str:
    try:
        from src._version import version
        return version
    except ImportError:
        pass
    try:
        from setuptools_scm import get_version as scm_version
        import os
        return scm_version(root=os.path.join(os.path.dirname(__file__), ".."), local_scheme="no-local-version")
    except Exception:
        return "dev"


__version__ = get_version()
