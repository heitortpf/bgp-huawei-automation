import re
import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def sanitize_filename(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return "SEM_NOME"
    s = s.replace(" ", "_")
    s = re.sub(r"[^a-zA-Z0-9._-]", "_", s)
    return s[:80]


def sha256_file(path: str) -> str:
    try:
        p = Path(path)
        if not p.exists() or not p.is_file():
            return "(arquivo não encontrado)"
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        return f"(falha ao calcular sha256: {e})"


def filesize_bytes(path: str) -> str:
    try:
        p = Path(path)
        if not p.exists() or not p.is_file():
            return "-"
        return str(p.stat().st_size)
    except Exception:
        return "-"
