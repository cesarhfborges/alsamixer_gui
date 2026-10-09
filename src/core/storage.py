import json
import os
import tempfile


def config_dir() -> str:
    """$XDG_CONFIG_HOME/alsamixer-gui (padrão ~/.config/alsamixer-gui)."""
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "alsamixer-gui")


def atomic_write_text(path: str, text: str) -> None:
    """Grava em arquivo temporário e substitui: nunca deixa o arquivo pela metade."""
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=os.path.splitext(path)[1])
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def atomic_write_json(path: str, data) -> None:
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False))
