import dataclasses
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).resolve().parent.parent / "historico.db"


def init_db() -> None:
    with sqlite3.connect(_DB_PATH) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp     TEXT NOT NULL,
                nome_cliente  TEXT NOT NULL,
                neighbor_ip   TEXT NOT NULL,
                local_as      INTEGER NOT NULL,
                neighbor_as   INTEGER NOT NULL,
                roteadores    TEXT NOT NULL,
                resultados    TEXT NOT NULL,
                relatorio_nome TEXT
            )
        """)


def salvar_sessao(sessao, routers, resultados, relatorio_nome: str | None) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    roteadores_json = json.dumps([r.host for r in routers], ensure_ascii=False)
    resultados_json = json.dumps([dataclasses.asdict(r) for r in resultados], ensure_ascii=False)
    try:
        with sqlite3.connect(_DB_PATH) as con:
            con.execute(
                """INSERT INTO sessions
                   (timestamp, nome_cliente, neighbor_ip, local_as, neighbor_as,
                    roteadores, resultados, relatorio_nome)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (ts, sessao.nome_cliente, sessao.neighbor_ip, sessao.local_as,
                 sessao.neighbor_as, roteadores_json, resultados_json, relatorio_nome),
            )
    except Exception as e:
        logger.error("Falha ao salvar sessão no histórico: %s", e)


def listar_sessoes(limit: int = 100) -> list[dict]:
    with sqlite3.connect(_DB_PATH) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT * FROM sessions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def buscar_sessao(id: int) -> dict | None:
    with sqlite3.connect(_DB_PATH) as con:
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM sessions WHERE id = ?", (id,)).fetchone()
    return _row_to_dict(row) if row else None


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["roteadores"] = json.loads(d["roteadores"])
    d["resultados"] = json.loads(d["resultados"])
    return d
