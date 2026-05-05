import socket
import time
import logging
from collections.abc import Callable
from datetime import datetime
from netmiko import ConnectHandler
from bgp.config import BACKUP_DIR, MAX_COMPROVANTE_CHARS
from bgp.models import RouterConfig, BgpSessionConfig, ExecutionResult
from bgp.utils import sanitize_filename, sha256_file, filesize_bytes

logger = logging.getLogger(__name__)


def _verificar_tcp(host: str, port: int, timeout: float = 5.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def _truncate(texto: str) -> str:
    texto = (texto or "").strip()
    if not texto:
        return "(sem saída)"
    if len(texto) > MAX_COMPROVANTE_CHARS:
        return texto[:MAX_COMPROVANTE_CHARS] + "\n\n...[TRUNCADO]..."
    return texto


def _run_include(conn, pattern: str) -> str:
    try:
        out = conn.send_command(f"display current-configuration | include {pattern}")
        return (out or "").strip()
    except Exception as e:
        logger.warning(f"Falha no include '{pattern}': {e}")
        return ""


def checar_config_existente(conn, session: BgpSessionConfig) -> str:
    patterns = [
        f"CLI-BGP-{session.nome_cliente}",
        f"{session.nome_cliente}-IPv4",
        f"{session.nome_cliente}-IPv6",
        f"bgp {session.local_as}",
        f"peer {session.neighbor_ip}",
        f"peer {session.neighbor_ip} as-number {session.neighbor_as}",
    ]
    achados = [
        f"### include: {p}\n{out}"
        for p in patterns
        if (out := _run_include(conn, p))
    ]
    return "\n\n".join(achados).strip()


def _salvar_backup(conn, host: str, nome_cliente: str) -> str:
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = BACKUP_DIR / f"backup_{sanitize_filename(host)}_{sanitize_filename(nome_cliente)}_{ts}.txt"
        cfg = conn.send_command("display current-configuration") or ""
        path.write_text(cfg, encoding="utf-8", errors="ignore")
        return str(path)
    except Exception as e:
        return f"(falha ao salvar backup: {e})"


def _coletar_display_bgp_peer(conn, neighbor_ip: str) -> str:
    try:
        return _truncate(conn.send_command(f"display bgp peer {neighbor_ip}"))
    except Exception as e:
        return f"(falha ao coletar display bgp peer: {e})"


def _coletar_bgp_display_this(conn, local_as: int) -> str:
    try:
        conn.send_command_timing("system-view")
        conn.send_command_timing(f"bgp {local_as}")
        out = conn.send_command_timing("display this")
        conn.send_command_timing("return")
        return _truncate(out)
    except Exception as e:
        return f"(falha ao coletar display this no bgp: {e})"


def _coletar_recorte_cliente(conn, session: BgpSessionConfig) -> str:
    patterns = [
        f"CLI-BGP-{session.nome_cliente}",
        f"{session.nome_cliente}-IPv4",
        f"{session.nome_cliente}-IPv6",
        f"peer {session.neighbor_ip} as-number {session.neighbor_as}",
    ]
    partes = [
        f"### include: {p}\n{out}"
        for p in patterns
        if (out := _run_include(conn, p))
    ]
    return _truncate("\n\n".join(partes) if partes else "(nada encontrado no recorte)")


def _emit(on_progress: Callable[[dict], None] | None, event: dict) -> None:
    if on_progress:
        on_progress(event)


def _executar_em_roteador(
    router: RouterConfig,
    session: BgpSessionConfig,
    cmds: list[str],
    confirmar_existente: Callable[[str, str], bool],
    on_progress: Callable[[dict], None] | None = None,
) -> ExecutionResult:
    inicio = time.time()
    resultado = ExecutionResult(host=router.host, status="ERRO", duracao_s=0.0)

    if not _verificar_tcp(router.host, router.port):
        resultado.status = f"ERRO: {router.host}:{router.port} inacessível (TCP)"
        resultado.duracao_s = round(time.time() - inicio, 2)
        logger.error(resultado.status)
        _emit(on_progress, {"type": "progress", "host": router.host, "step": "tcp_check",
                            "msg": f"TCP {router.host}:{router.port} → FALHOU"})
        return resultado

    _emit(on_progress, {"type": "progress", "host": router.host, "step": "tcp_check",
                        "msg": f"TCP {router.host}:{router.port} → OK"})

    conn = None
    try:
        logger.info(f"Conectando ao roteador {router.host}...")
        conn = ConnectHandler(
            device_type="huawei",
            host=router.host,
            username=router.username,
            password=router.password,
            port=router.port,
            fast_cli=False,
        )
        logger.info(f"Conectado a {router.host}.")
        _emit(on_progress, {"type": "progress", "host": router.host, "step": "ssh_connected",
                            "msg": f"SSH conectado"})

        existente = checar_config_existente(conn, session)
        if not confirmar_existente(router.host, existente):
            conn.disconnect()
            resultado.status = "PULADO (já existia config)"
            resultado.duracao_s = round(time.time() - inicio, 2)
            resultado.display_bgp_peer = "(não coletado: roteador pulado)"
            resultado.bgp_display_this = "(não coletado: roteador pulado)"
            resultado.recorte_cliente = "(não coletado: roteador pulado)"
            logger.info(f"{router.host} -> {resultado.status} em {resultado.duracao_s}s")
            return resultado

        backup_path = _salvar_backup(conn, router.host, session.nome_cliente)
        resultado.backup_path = backup_path
        if backup_path and not backup_path.startswith("("):
            resultado.backup_sha256 = sha256_file(backup_path)
            resultado.backup_size = filesize_bytes(backup_path)
        logger.info(f"Backup ({router.host}): {backup_path} | SHA256: {resultado.backup_sha256}")
        _emit(on_progress, {"type": "progress", "host": router.host, "step": "backup_done",
                            "msg": f"Backup salvo ({resultado.backup_size})"})

        conn.send_config_set(cmds)
        _emit(on_progress, {"type": "progress", "host": router.host, "step": "commands_sent",
                            "msg": "Comandos aplicados"})

        display_peer = _coletar_display_bgp_peer(conn, session.neighbor_ip)
        resultado.display_bgp_peer = display_peer
        resultado.bgp_display_this = _coletar_bgp_display_this(conn, session.local_as)
        resultado.recorte_cliente = _coletar_recorte_cliente(conn, session)
        conn.disconnect()

        bgp_status = "Established" if "Established" in display_peer else "Não estabelecido"
        resultado.status = "SUCESSO (Established)" if "Established" in display_peer else "BGP NÃO ESTABELECIDO"
        resultado.duracao_s = round(time.time() - inicio, 2)
        logger.info(f"{router.host} -> {resultado.status} em {resultado.duracao_s}s")
        _emit(on_progress, {"type": "progress", "host": router.host, "step": "verification_done",
                            "msg": f"BGP peer: {bgp_status}"})

    except Exception as e:
        if conn is not None:
            try:
                conn.disconnect()
            except Exception:
                pass
        resultado.status = f"ERRO: {e}"
        resultado.duracao_s = round(time.time() - inicio, 2)
        logger.error(f"Erro em {router.host}: {e}")

    return resultado


def executar_bgp(
    routers: list[RouterConfig],
    session: BgpSessionConfig,
    cmds: list[str],
    confirmar_existente: Callable[[str, str], bool],
    on_progress: Callable[[dict], None] | None = None,
) -> list[ExecutionResult]:
    resultados = []
    for r in routers:
        res = _executar_em_roteador(r, session, cmds, confirmar_existente, on_progress)
        resultados.append(res)
        _emit(on_progress, {"type": "result", "host": res.host, "status": res.status,
                            "duracao_s": res.duracao_s})
    return resultados
