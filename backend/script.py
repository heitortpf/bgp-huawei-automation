import time
import sys
import socket
import ipaddress
from datetime import datetime
from pathlib import Path

from netmiko import ConnectHandler
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Preformatted, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
import logging
import re
import hashlib
import os

# ================= CONFIG =================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ARQUIVO_ROUTERS = "routers.txt"
EMPRESA = "SEU ISP"

MAX_COMPROVANTE_CHARS = 12000  # limite por bloco de saída no PDF
BACKUP_DIR = Path("backups")

# ================= HELPERS =================

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

# ================= INPUTS =================

def obter_as_local():
    while True:
        try:
            local_as = int(input("Informe o AS LOCAL: ").strip())
            if not (1 <= local_as <= 4294967295):
                raise ValueError
            return local_as
        except ValueError:
            logger.error("AS LOCAL inválido. Tente novamente.")

def obter_ip_neigh():
    while True:
        try:
            return str(ipaddress.ip_address(input("Informe o IP do NEIGHBOR BGP: ").strip()))
        except ValueError:
            logger.error("IP do neighbor inválido. Tente novamente.")

def obter_as_neigh():
    while True:
        try:
            neighbor_as = int(input("Informe o AS DO NEIGHBOR: ").strip())
            if not (1 <= neighbor_as <= 4294967295):
                raise ValueError
            return neighbor_as
        except ValueError:
            logger.error("AS do neighbor inválido. Tente novamente.")

def obter_nome_cliente():
    nome_cliente = input("Informe o nome do cliente (sem espaços, se puder): ").strip()
    if not nome_cliente:
        logger.error("Nome do cliente não pode ser vazio.")
        return obter_nome_cliente()
    return nome_cliente

def escolher_tipo_prefixo():
    print("\n=== TIPO DE PREFIXO ===")
    print("1 - Apenas IPv4")
    print("2 - Apenas IPv6")
    print("3 - IPv4 e IPv6")
    while True:
        opcao = input("Escolha (1/2/3): ").strip()
        if opcao in ("1", "2", "3"):
            return opcao
        logger.error("Opção inválida.")

def obter_prefixo_ipv4():
    while True:
        try:
            return str(ipaddress.ip_network(input("Prefixo IPv4 (ex: 203.0.113.0/24): ").strip(), strict=False))
        except ValueError:
            logger.error("Prefixo IPv4 inválido. Tente novamente.")

def obter_prefixo_ipv6():
    while True:
        try:
            return str(ipaddress.ip_network(input("Prefixo IPv6 (ex: 2001:db8::/32): ").strip(), strict=False))
        except ValueError:
            logger.error("Prefixo IPv6 inválido. Tente novamente.")

def adicionar_prefixos_ipv4():
    prefixes = []
    print("\n=== PREFIXOS IPv4 ===")
    while True:
        prefixes.append(obter_prefixo_ipv4())
        if input("Adicionar mais um IPv4? (s/n): ").strip().lower() != "s":
            break
    return prefixes

def adicionar_prefixos_ipv6():
    prefixes = []
    print("\n=== PREFIXOS IPv6 ===")
    while True:
        prefixes.append(obter_prefixo_ipv6())
        if input("Adicionar mais um IPv6? (s/n): ").strip().lower() != "s":
            break
    return prefixes

def perguntar_preview():
    return input("\nDeseja ver o preview dos comandos antes de aplicar? (s/n): ").strip().lower() == "s"

def perguntar_validacao_irr():
    return input("Deseja validar IRR (RADB) antes de aplicar? (s/n): ").strip().lower() == "s"

# ================= NOMES AUTO =================

def gerar_policies_e_prefixos(nome_cliente):
    nome_prefix_ipv4 = f"{nome_cliente}-IPv4"
    rp_imp_v4 = f"CLI-BGP-{nome_cliente}-IPv4-IMPORT"
    rp_exp_v4 = f"CLI-BGP-{nome_cliente}-IPv4-EXPORT"

    nome_prefix_ipv6 = f"{nome_cliente}-IPv6"
    rp_imp_v6 = f"CLI-BGP-{nome_cliente}-IPv6-IMPORT"
    rp_exp_v6 = f"CLI-BGP-{nome_cliente}-IPv6-EXPORT"

    return (nome_prefix_ipv4, rp_imp_v4, rp_exp_v4,
            nome_prefix_ipv6, rp_imp_v6, rp_exp_v6)

# ================= IRR (RADB) =================

def validar_asn_prefixo(prefixos, asn_peer):
    logger.info("Validando prefixos contra ASN via IRR (RADB)...")

    WHOIS_SERVER = "whois.radb.net"
    WHOIS_PORT = 43
    origins_encontrados = set()

    try:
        for prefixo in prefixos:
            with socket.create_connection((WHOIS_SERVER, WHOIS_PORT), timeout=10) as s:
                s.sendall(f"{prefixo}\n".encode())

                resposta = b""
                while True:
                    data = s.recv(4096)
                    if not data:
                        break
                    resposta += data

            resposta_txt = resposta.decode(errors="ignore").lower().splitlines()

            rota_atual = None
            for linha in resposta_txt:
                linha = linha.strip()
                if linha.startswith("route:") or linha.startswith("route6:"):
                    rota_atual = linha.split(":", 1)[1].strip()

                if linha.startswith("origin:") and rota_atual:
                    asn = linha.split(":", 1)[1].strip().replace("as", "")
                    origins_encontrados.add(asn)

    except Exception as e:
        logger.error(f"Erro ao consultar IRR/RADB: {e}")
        sys.exit(1)

    if str(asn_peer) not in origins_encontrados:
        logger.error("Erro crítico de validação IRR.")
        logger.error(f"ASN do peer informado: AS{asn_peer}")
        logger.error(f"ASN(s) encontrados no IRR: {', '.join(origins_encontrados) or 'nenhum'}")
        sys.exit(1)

    logger.info("Validação IRR OK: origin ASN confere com ASN do peer.")

# ================= CONFIRMAÇÃO =================

def confirmacao(local_as, neighbor_ip, neighbor_as, nome_cliente,
                prefixes_ipv4, prefixes_ipv6,
                nome_prefix_ipv4, nome_prefix_ipv6,
                rp_imp_v4, rp_exp_v4, rp_imp_v6, rp_exp_v6):

    logger.info("=== CONFIRMAÇÃO ===")
    print(f"AS LOCAL: {local_as}")
    print(f"NEIGHBOR: {neighbor_ip} AS {neighbor_as}")
    print(f"CLIENTE: {nome_cliente}")

    if prefixes_ipv4:
        print(f"PREFIX-LIST IPv4: {nome_prefix_ipv4} -> {', '.join(prefixes_ipv4)}")
        print(f"ROUTE-POLICY IPv4: IMPORT {rp_imp_v4} | EXPORT {rp_exp_v4}")
    else:
        print("IPv4: (não será configurado)")

    if prefixes_ipv6:
        print(f"PREFIX-LIST IPv6: {nome_prefix_ipv6} -> {', '.join(prefixes_ipv6)}")
        print(f"ROUTE-POLICY IPv6: IMPORT {rp_imp_v6} | EXPORT {rp_exp_v6}")
    else:
        print("IPv6: (não será configurado)")

    if input("\nDeseja aplicar essas configurações? (s/n): ").strip().lower() != 's':
        logger.info("Operação cancelada pelo usuário.")
        sys.exit(0)

# ================= ROTEADORES =================

def ler_routers_txt():
    routers = []
    try:
        with open(ARQUIVO_ROUTERS, encoding="utf-8") as f:
            for l in f:
                l = l.strip()
                if not l or l.startswith("#"):
                    continue
                host, user, pwd, port = l.split(",")
                routers.append({
                    "host": host.strip(),
                    "username": user.strip(),
                    "password": pwd.strip(),
                    "port": int(port.strip())
                })
    except Exception as e:
        logger.error(f"Erro ao ler o arquivo de roteadores: {e}")
        sys.exit(1)

    return routers

def escolher_roteadores(routers_all):
    print("\n=== SELEÇÃO DE ROTEADORES ===")
    print("1 - Aplicar em TODOS os roteadores")
    print("2 - Aplicar em APENAS UM roteador")

    opcao = input("Escolha (1/2): ").strip()

    if opcao == "1":
        return routers_all

    if opcao == "2":
        for i, r in enumerate(routers_all, 1):
            print(f"{i} - {r['host']}")
        try:
            escolha = int(input("Escolha o número: ").strip())
            return [routers_all[escolha - 1]]
        except Exception:
            logger.error("Seleção inválida.")
            sys.exit(1)

    logger.error("Opção inválida.")
    sys.exit(1)

# ================= BUILD COMMANDS (NE8000 F1A/M4) =================

def build_huawei_commands(local_as, neighbor_ip, neighbor_as,
                         nome_prefix_ipv4, nome_prefix_ipv6,
                         prefixes_ipv4, prefixes_ipv6,
                         rp_imp_v4, rp_exp_v4, rp_imp_v6, rp_exp_v6):

    cmds = []
    cmds.append("system-view")

    if prefixes_ipv4:
        for index, pfx in enumerate(prefixes_ipv4, start=10):
            cmds.append(f"ip ip-prefix {nome_prefix_ipv4} index {index} permit {pfx}")

        cmds.append(f"route-policy {rp_imp_v4} permit node 10")
        cmds.append(f" if-match ip-prefix {nome_prefix_ipv4}")
        cmds.append(" quit")
        cmds.append(f"route-policy {rp_imp_v4} deny node 500")
        cmds.append(" quit")

        cmds.append(f"route-policy {rp_exp_v4} permit node 10")
        cmds.append(" quit")
        cmds.append(f"route-policy {rp_exp_v4} deny node 500")
        cmds.append(" quit")

    if prefixes_ipv6:
        for index, pfx in enumerate(prefixes_ipv6, start=10):
            cmds.append(f"ip ipv6-prefix {nome_prefix_ipv6} index {index} permit {pfx}")

        cmds.append(f"route-policy {rp_imp_v6} permit node 10")
        cmds.append(f" if-match ipv6 address prefix-list {nome_prefix_ipv6}")
        cmds.append(" quit")
        cmds.append(f"route-policy {rp_imp_v6} deny node 500")
        cmds.append(" quit")

        cmds.append(f"route-policy {rp_exp_v6} permit node 10")
        cmds.append(" quit")
        cmds.append(f"route-policy {rp_exp_v6} deny node 500")
        cmds.append(" quit")

    cmds.append(f"bgp {local_as}")
    cmds.append(f" peer {neighbor_ip} as-number {neighbor_as}")

    if prefixes_ipv4:
        cmds.append(" ipv4-family unicast")
        cmds.append(f"  peer {neighbor_ip} enable")
        cmds.append(f"  peer {neighbor_ip} route-policy {rp_imp_v4} import")
        cmds.append(f"  peer {neighbor_ip} route-policy {rp_exp_v4} export")

    if prefixes_ipv6:
        cmds.append(" ipv6-family unicast")
        cmds.append(f"  peer {neighbor_ip} enable")
        cmds.append(f"  peer {neighbor_ip} route-policy {rp_imp_v6} import")
        cmds.append(f"  peer {neighbor_ip} route-policy {rp_exp_v6} export")

    cmds.append("return")
    return cmds

def preview_commands(cmds):
    print("\n=== PREVIEW DOS COMANDOS (Huawei NE8000) ===")
    for c in cmds:
        print(c)
    print("=== FIM DO PREVIEW ===\n")

# ================= CHECAGEM EXISTENTE (AMARRADA) =================

def _run_include(conn, pattern: str) -> str:
    try:
        out = conn.send_command(f"display current-configuration | include {pattern}")
        return (out or "").strip()
    except Exception as e:
        logger.warning(f"Falha no include '{pattern}': {e}")
        return ""

def checar_config_existente_amarrado(conn, nome_cliente: str, neighbor_ip: str, local_as: int, neighbor_as: int) -> str:
    patterns = [
        f"CLI-BGP-{nome_cliente}",
        f"{nome_cliente}-IPv4",
        f"{nome_cliente}-IPv6",
        f"bgp {local_as}",
        f"peer {neighbor_ip}",
        f"peer {neighbor_ip} as-number {neighbor_as}",
    ]

    achados = []
    for p in patterns:
        out = _run_include(conn, p)
        if out:
            achados.append(f"### include: {p}\n{out}")

    return "\n\n".join(achados).strip()

def decidir_aplicar_quando_existe(host: str, existente: str) -> bool:
    if not existente:
        return True

    print(f"\n⚠️  Encontrado config relacionada neste roteador: {host}")
    print("----------------------------------------")
    print(existente)
    print("----------------------------------------")
    return input("Quer aplicar mesmo assim neste roteador? (s/n): ").strip().lower() == "s"

# ================= BACKUP PRE-CHANGE =================

def salvar_backup_current_config(conn, host: str, nome_cliente: str) -> str:
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_host = sanitize_filename(host)
        safe_cli = sanitize_filename(nome_cliente)
        path = BACKUP_DIR / f"backup_{safe_host}_{safe_cli}_{ts}.txt"

        cfg = conn.send_command("display current-configuration") or ""
        path.write_text(cfg, encoding="utf-8", errors="ignore")
        return str(path)

    except Exception as e:
        return f"(falha ao salvar backup: {e})"

# ================= COLETAS PÓS-APLICAÇÃO =================

def _truncate(texto: str, limite: int = MAX_COMPROVANTE_CHARS) -> str:
    texto = (texto or "").strip()
    if not texto:
        return "(sem saída)"
    if len(texto) > limite:
        return texto[:limite] + "\n\n...[TRUNCADO]..."
    return texto

def coletar_display_bgp_peer(conn, neighbor_ip: str) -> str:
    try:
        out = conn.send_command(f"display bgp peer {neighbor_ip}")
        return _truncate(out)
    except Exception as e:
        return f"(falha ao coletar display bgp peer: {e})"

def coletar_bgp_display_this(conn, local_as: int) -> str:
    try:
        conn.send_command_timing("system-view")
        conn.send_command_timing(f"bgp {local_as}")
        out = conn.send_command_timing("display this")
        conn.send_command_timing("return")
        return _truncate(out)
    except Exception as e:
        return f"(falha ao coletar display this no bgp: {e})"

def coletar_recorte_cliente(conn, nome_cliente: str, neighbor_ip: str, neighbor_as: int) -> str:
    patterns = [
        f"CLI-BGP-{nome_cliente}",
        f"{nome_cliente}-IPv4",
        f"{nome_cliente}-IPv6",
        f"peer {neighbor_ip} as-number {neighbor_as}",
    ]
    partes = []
    for p in patterns:
        out = _run_include(conn, p)
        if out:
            partes.append(f"### include: {p}\n{out}")

    return _truncate("\n\n".join(partes) if partes else "(nada encontrado no recorte)")

# ================= EXECUÇÃO =================

def executar_bgp(routers, local_as, neighbor_ip, neighbor_as,
                 nome_cliente,
                 nome_prefix_ipv4, nome_prefix_ipv6,
                 prefixes_ipv4, prefixes_ipv6,
                 rp_imp_v4, rp_exp_v4, rp_imp_v6, rp_exp_v6):

    resultados = []
    cmds = build_huawei_commands(
        local_as, neighbor_ip, neighbor_as,
        nome_prefix_ipv4, nome_prefix_ipv6,
        prefixes_ipv4, prefixes_ipv6,
        rp_imp_v4, rp_exp_v4, rp_imp_v6, rp_exp_v6
    )

    for r in routers:
        inicio = time.time()
        backup_path = "(não gerado)"
        backup_sha256 = "-"
        backup_size = "-"

        try:
            logger.info(f"Conectando ao roteador {r['host']}...")
            device = {
                "device_type": "huawei",
                "host": r['host'],
                "username": r['username'],
                "password": r['password'],
                "port": r['port'],
                "fast_cli": False
            }
            conn = ConnectHandler(**device)
            logger.info(f"Conectado a {r['host']}.")

            existente = checar_config_existente_amarrado(conn, nome_cliente, neighbor_ip, local_as, neighbor_as)
            aplicar = decidir_aplicar_quando_existe(r["host"], existente)

            if not aplicar:
                dur = round(time.time() - inicio, 2)
                conn.disconnect()
                logger.info(f"{r['host']} -> PULADO (já existia config) em {dur}s")

                resultados.append({
                    "host": r["host"],
                    "status": "PULADO (já existia config)",
                    "duracao_s": dur,
                    "backup_path": backup_path,
                    "backup_sha256": backup_sha256,
                    "backup_size": backup_size,
                    "display_bgp_peer": "(não coletado: roteador pulado)",
                    "bgp_display_this": "(não coletado: roteador pulado)",
                    "recorte_cliente": "(não coletado: roteador pulado)",
                })
                continue

            # Backup só quando for aplicar
            backup_path = salvar_backup_current_config(conn, r["host"], nome_cliente)
            if backup_path and not backup_path.startswith("("):
                backup_sha256 = sha256_file(backup_path)
                backup_size = filesize_bytes(backup_path)

            logger.info(f"Backup ({r['host']}): {backup_path}")
            logger.info(f"SHA256 backup ({r['host']}): {backup_sha256}")

            # aplica config
            conn.send_config_set(cmds)

            # coleta status e comprovantes
            display_peer = coletar_display_bgp_peer(conn, neighbor_ip)
            status = "SUCESSO (Established)" if "Established" in display_peer else "BGP NÃO ESTABELECIDO"

            bgp_this = coletar_bgp_display_this(conn, local_as)
            recorte = coletar_recorte_cliente(conn, nome_cliente, neighbor_ip, neighbor_as)

            dur = round(time.time() - inicio, 2)
            conn.disconnect()

            logger.info(f"{r['host']} -> {status} em {dur}s")
            resultados.append({
                "host": r["host"],
                "status": status,
                "duracao_s": dur,
                "backup_path": backup_path,
                "backup_sha256": backup_sha256,
                "backup_size": backup_size,
                "display_bgp_peer": display_peer,
                "bgp_display_this": bgp_this,
                "recorte_cliente": recorte,
            })

        except Exception as e:
            dur = round(time.time() - inicio, 2)
            logger.error(f"Erro em {r['host']}: {e}")
            resultados.append({
                "host": r["host"],
                "status": f"ERRO: {e}",
                "duracao_s": dur,
                "backup_path": backup_path,
                "backup_sha256": backup_sha256,
                "backup_size": backup_size,
                "display_bgp_peer": "(não coletado: erro)",
                "bgp_display_this": "(não coletado: erro)",
                "recorte_cliente": "(não coletado: erro)",
            })

    return resultados

# ================= PDF BUILD (COM HASH NO FINAL) =================

def _build_pdf(path_pdf: str, resultados,
               pdf_sha256: str, pdf_size: str,
               routers_txt_path: str, routers_txt_sha256: str, routers_txt_size: str):

    doc = SimpleDocTemplate(path_pdf, pagesize=A4)
    styles = getSampleStyleSheet()

    code_style = ParagraphStyle(
        name="CodeBlock",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8.3,
        leading=10,
        alignment=TA_LEFT
    )

    elems = []
    elems.append(Paragraph("Relatório Automação BGP Huawei (NE8000)", styles['Title']))
    elems.append(Paragraph(f"Empresa: {EMPRESA}", styles['Normal']))
    elems.append(Paragraph(datetime.now().strftime('%d/%m/%Y %H:%M:%S'), styles['Normal']))
    elems.append(Spacer(1, 12))

    tabela = [["Roteador", "Status", "Duração (s)", "Backup", "Tam (bytes)", "SHA256 (backup)"]]
    for r in resultados:
        tabela.append([
            r['host'],
            r['status'],
            str(r.get("duracao_s", "-")),
            r.get("backup_path", "-"),
            r.get("backup_size", "-"),
            r.get("backup_sha256", "-"),
        ])

    t = Table(tabela, repeatRows=1, colWidths=[80, 95, 55, 120, 55, 140])
    t.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTSIZE', (0, 0), (-1, -1), 7.3),
    ]))

    elems.append(t)
    elems.append(PageBreak())

    elems.append(Paragraph("Auditoria por roteador", styles["Heading2"]))
    elems.append(Spacer(1, 10))

    for idx, r in enumerate(resultados, start=1):
        elems.append(Paragraph(f"{idx}. Roteador: {r['host']}", styles["Heading3"]))
        elems.append(Paragraph(
            f"Status: {r['status']} | Duração: {r.get('duracao_s', '-') }s",
            styles["Normal"]
        ))
        elems.append(Paragraph(
            f"Backup: {r.get('backup_path', '-')} | Tam (bytes): {r.get('backup_size', '-') }",
            styles["Normal"]
        ))
        elems.append(Paragraph(
            f"SHA256 (backup): {r.get('backup_sha256', '-')}",
            styles["Normal"]
        ))
        elems.append(Spacer(1, 10))

        elems.append(Paragraph("1) display bgp peer", styles["Heading4"]))
        elems.append(Preformatted(r.get("display_bgp_peer", ""), code_style))
        elems.append(Spacer(1, 12))

        elems.append(Paragraph("2) BGP (display this)", styles["Heading4"]))
        elems.append(Preformatted(r.get("bgp_display_this", ""), code_style))
        elems.append(Spacer(1, 12))

        elems.append(Paragraph("3) Recorte do current-configuration (cliente/policies/prefix-lists/peer)", styles["Heading4"]))
        elems.append(Preformatted(r.get("recorte_cliente", ""), code_style))
        elems.append(Spacer(1, 16))

        elems.append(PageBreak())

    # Página final com integridade do relatório
    elems.append(Paragraph("Integridade do Relatório", styles["Heading2"]))
    elems.append(Spacer(1, 12))

    elems.append(Paragraph("SHA256 do próprio PDF (auditoria):", styles["Normal"]))
    elems.append(Preformatted(pdf_sha256, code_style))
    elems.append(Paragraph(f"Tamanho do PDF (bytes): {pdf_size}", styles["Normal"]))
    elems.append(Spacer(1, 12))

    elems.append(Paragraph("Inventário utilizado (routers.txt):", styles["Normal"]))
    elems.append(Paragraph(f"Caminho: {routers_txt_path}", styles["Normal"]))
    elems.append(Paragraph(f"Tamanho (bytes): {routers_txt_size}", styles["Normal"]))
    elems.append(Paragraph("SHA256 (routers.txt):", styles["Normal"]))
    elems.append(Preformatted(routers_txt_sha256, code_style))

    doc.build(elems)

def gerar_relatorio(resultados):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    pdf_tmp = f"relatorio_huawei_{ts}_tmp.pdf"
    pdf_final = f"relatorio_huawei_{ts}.pdf"

    routers_path_abs = str(Path(ARQUIVO_ROUTERS).resolve())
    routers_sha = sha256_file(routers_path_abs)
    routers_size = filesize_bytes(routers_path_abs)

    # 1) gera um PDF temporário (hash placeholder)
    _build_pdf(
        pdf_tmp,
        resultados,
        pdf_sha256="(calculando...)",
        pdf_size="-",
        routers_txt_path=routers_path_abs,
        routers_txt_sha256=routers_sha,
        routers_txt_size=routers_size
    )

    # 2) calcula hash e tamanho do PDF temporário
    pdf_hash = sha256_file(pdf_tmp)
    pdf_size = filesize_bytes(pdf_tmp)

    # 3) gera o PDF final já com hash correto
    _build_pdf(
        pdf_final,
        resultados,
        pdf_sha256=pdf_hash,
        pdf_size=pdf_size,
        routers_txt_path=routers_path_abs,
        routers_txt_sha256=routers_sha,
        routers_txt_size=routers_size
    )

    # 4) apaga o temporário
    try:
        os.remove(pdf_tmp)
    except Exception:
        pass

    logger.info(f"Relatório gerado: {pdf_final}")
    logger.info(f"SHA256 do PDF: {pdf_hash}")
    logger.info(f"routers.txt: {routers_path_abs} | SHA256: {routers_sha}")

    return pdf_final, pdf_hash, routers_sha

# ================= MAIN =================

def main():
    local_as = obter_as_local()
    neighbor_ip = obter_ip_neigh()
    neighbor_as = obter_as_neigh()
    nome_cliente = obter_nome_cliente()

    tipo = escolher_tipo_prefixo()

    prefixes_ipv4 = []
    prefixes_ipv6 = []

    if tipo == "1":
        prefixes_ipv4 = adicionar_prefixos_ipv4()
    elif tipo == "2":
        prefixes_ipv6 = adicionar_prefixos_ipv6()
    else:
        prefixes_ipv4 = adicionar_prefixos_ipv4()
        prefixes_ipv6 = adicionar_prefixos_ipv6()

    (nome_prefix_ipv4, rp_imp_v4, rp_exp_v4,
     nome_prefix_ipv6, rp_imp_v6, rp_exp_v6) = gerar_policies_e_prefixos(nome_cliente)

    cmds = build_huawei_commands(
        local_as, neighbor_ip, neighbor_as,
        nome_prefix_ipv4, nome_prefix_ipv6,
        prefixes_ipv4, prefixes_ipv6,
        rp_imp_v4, rp_exp_v4, rp_imp_v6, rp_exp_v6
    )

    if perguntar_preview():
        preview_commands(cmds)

    if perguntar_validacao_irr():
        validar_asn_prefixo(prefixes_ipv4 + prefixes_ipv6, neighbor_as)

    confirmacao(
        local_as, neighbor_ip, neighbor_as, nome_cliente,
        prefixes_ipv4, prefixes_ipv6,
        nome_prefix_ipv4, nome_prefix_ipv6,
        rp_imp_v4, rp_exp_v4, rp_imp_v6, rp_exp_v6
    )

    routers_all = ler_routers_txt()
    routers = escolher_roteadores(routers_all)

    resultados = executar_bgp(
        routers, local_as, neighbor_ip, neighbor_as,
        nome_cliente,
        nome_prefix_ipv4, nome_prefix_ipv6,
        prefixes_ipv4, prefixes_ipv6,
        rp_imp_v4, rp_exp_v4, rp_imp_v6, rp_exp_v6
    )

    pdf_path, pdf_hash, routers_hash = gerar_relatorio(resultados)
    print(f"\n✅ PDF gerado: {pdf_path}")
    print(f"✅ SHA256 do PDF: {pdf_hash}")
    print(f"✅ SHA256 do routers.txt: {routers_hash}")
    print(f"✅ Backups em: {BACKUP_DIR.resolve()}\n")

if __name__ == "__main__":
    main()
