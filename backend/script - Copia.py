import time
import sys
import socket
import ipaddress
from datetime import datetime
from netmiko import ConnectHandler
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
import logging

# Configuração de logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Definindo constantes
ARQUIVO_ROUTERS = "routers.txt"
EMPRESA = "SEU ISP"

# Variáveis globais para armazenar os prefixos
prefixes_ipv4 = []
prefixes_ipv6 = []

# ================= FUNÇÕES DE ENTRADA =================

def obter_as_local():
    while True:
        try:
            local_as = int(input("Informe o AS LOCAL: "))
            if not (1 <= local_as <= 4294967295):
                raise ValueError
            return local_as
        except ValueError:
            logger.error("AS LOCAL inválido. Tente novamente.")

def obter_ip_neigh():
    while True:
        try:
            return str(ipaddress.ip_address(input("Informe o IP do NEIGHBOR BGP: ")))
        except ValueError:
            logger.error("IP do neighbor inválido. Tente novamente.")

def obter_as_neigh():
    while True:
        try:
            neighbor_as = int(input("Informe o AS DO NEIGHBOR: "))
            if not (1 <= neighbor_as <= 4294967295):
                raise ValueError
            return neighbor_as
        except ValueError:
            logger.error("AS do neighbor inválido. Tente novamente.")

def obter_nome_cliente():
    """
    Função para obter o nome do cliente. Este nome será usado na nomenclatura automática das policies e prefixos.
    """
    nome_cliente = input("Informe o nome do cliente: ")
    return nome_cliente

# Função para obter o prefixo IPv4
def obter_prefixo_ipv4():
    while True:
        try:
            return str(ipaddress.ip_network(input("Prefixo IPv4 a anunciar (ex: 203.0.113.0/24): "), strict=False))
        except ValueError:
            logger.error("Prefixo IPv4 inválido. Tente novamente.")

# Função para obter o prefixo IPv6
def obter_prefixo_ipv6():
    while True:
        try:
            return str(ipaddress.ip_network(input("Prefixo IPv6 a anunciar (ex: 2001:db8::/32): "), strict=False))
        except ValueError:
            logger.error("Prefixo IPv6 inválido. Tente novamente.")

# ================= GERAÇÃO AUTOMÁTICA DE POLÍTICAS E PREFIXOS =================

def gerar_policies_e_prefixos(nome_cliente):
    """
    Função que gera automaticamente as nomenclaturas das policies e prefixos com base no nome do cliente.
    """
    # Gerando as nomenclaturas automáticas para IPv4
    nome_prefix_ipv4 = f"{nome_cliente}-IPv4"
    route_policy_import_ipv4 = f"CLI-BGP-{nome_cliente}-IPv4-IMPORT"
    route_policy_export_ipv4 = f"CLI-BGP-{nome_cliente}-IPv4-EXPORT"
    
    # Gerando as nomenclaturas automáticas para IPv6
    nome_prefix_ipv6 = f"{nome_cliente}-IPv6"
    route_policy_import_ipv6 = f"CLI-BGP-{nome_cliente}-IPv6-IMPORT"
    route_policy_export_ipv6 = f"CLI-BGP-{nome_cliente}-IPv6-EXPORT"
    
    # Retornando as nomenclaturas de políticas e prefixos
    return nome_prefix_ipv4, route_policy_import_ipv4, route_policy_export_ipv4, nome_prefix_ipv6, route_policy_import_ipv6, route_policy_export_ipv6

# ================= FUNÇÃO PARA ADICIONAR PREFIXOS =================

def adicionar_prefixos_ipv4():
    """
    Função para permitir ao usuário adicionar múltiplos prefixos IPv4.
    """
    global prefixes_ipv4
    while True:
        prefixo = obter_prefixo_ipv4()  # Obter prefixo IPv4
        prefixes_ipv4.append(prefixo)  # Armazenando o prefixo IPv4

        adicionar_mais = input("Deseja adicionar mais um prefixo IPv4? (s/n): ").lower()
        if adicionar_mais != "s":
            break

# Função para adicionar múltiplos prefixos IPv6
def adicionar_prefixos_ipv6():
    """
    Função para permitir ao usuário adicionar múltiplos prefixos IPv6.
    """
    global prefixes_ipv6
    while True:
        prefixo = obter_prefixo_ipv6()  # Obter prefixo IPv6
        prefixes_ipv6.append(prefixo)  # Armazenando o prefixo IPv6

        adicionar_mais = input("Deseja adicionar mais um prefixo IPv6? (s/n): ").lower()
        if adicionar_mais != "s":
            break

# ================= VALIDAÇÃO ASN x PREFIXO =================

def validar_asn_prefixo(prefixos, asn_peer):
    logger.info("Validando prefixos contra ASN via IRR (RADB)...")
    
    WHOIS_SERVER = "whois.radb.net"
    WHOIS_PORT = 43
    origins_encontrados = set()

    try:
        for prefixo in prefixos:  # Validando todos os prefixos
            with socket.create_connection((WHOIS_SERVER, WHOIS_PORT), timeout=10) as s:
                query = f"{prefixo}\n"
                s.sendall(query.encode())

                resposta = b""
                while True:
                    data = s.recv(4096)
                    if not data:
                        break
                    resposta += data

            resposta_txt = resposta.decode(errors="ignore").lower().splitlines()

            # Adicionando log da resposta completa para depuração
            logger.debug(f"Resposta do RADB para o prefixo {prefixo}: {resposta_txt}")

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

def confirmacao(local_as, neighbor_ip, neighbor_as, nome_cliente, prefixes_ipv4, prefixes_ipv6, route_policy_import_ipv4, route_policy_export_ipv4, route_policy_import_ipv6, route_policy_export_ipv6):
    logger.info("=== CONFIRMAÇÃO ===")
    print(f"AS LOCAL: {local_as}")
    print(f"NEIGHBOR: {neighbor_ip} AS {neighbor_as}")

    # Exibindo os prefixos IPv4 e IPv6 corretamente
    nome_prefix_ipv4 = f"{nome_cliente}-IPv4"
    nome_prefix_ipv6 = f"{nome_cliente}-IPv6"
    
    print(f"PREFIX-LIST IPv4: {nome_prefix_ipv4} -> {', '.join(prefixes_ipv4)}")
    print(f"PREFIX-LIST IPv6: {nome_prefix_ipv6} -> {', '.join(prefixes_ipv6)}")
    print(f"ROUTE-POLICY IMPORT IPv4: {route_policy_import_ipv4}")
    print(f"ROUTE-POLICY EXPORT IPv4: {route_policy_export_ipv4}")
    print(f"ROUTE-POLICY IMPORT IPv6: {route_policy_import_ipv6}")
    print(f"ROUTE-POLICY EXPORT IPv6: {route_policy_export_ipv6}")

    if input("Deseja aplicar essas configurações? (s/n): ").lower() != 's':
        logger.info("Operação cancelada pelo usuário.")
        sys.exit(0)

# ================= LEITURA DE ROTEADORES =================

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

# ================= SELEÇÃO DE ROTEADORES =================

def escolher_roteadores(routers_all):
    print("\n=== SELEÇÃO DE ROTEADORES ===")
    print("1 - Aplicar em TODOS os roteadores")
    print("2 - Aplicar em APENAS UM roteador")

    opcao = input("Escolha (1/2): ")

    if opcao == "1":
        return routers_all
    elif opcao == "2":
        for i, r in enumerate(routers_all, 1):
            print(f"{i} - {r['host']}")
        try:
            escolha = int(input("Escolha o número: "))
            return [routers_all[escolha - 1]]
        except Exception:
            logger.error("Seleção inválida.")
            sys.exit(1)
    else:
        logger.error("Opção inválida.")
        sys.exit(1)

# ================= EXECUÇÃO BGP =================

def executar_bgp(routers, local_as, neighbor_ip, neighbor_as, prefixes_ipv4, route_policy_import_ipv4, route_policy_export_ipv4, prefixes_ipv6, route_policy_import_ipv6, route_policy_export_ipv6):
    resultados = []
    for r in routers:
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

            # Criar as políticas de importação e exportação
            cmds = []

            # Configuração do import IPv4: permite apenas os prefixos definidos
            cmds.append(f"route-policy {route_policy_import_ipv4} permit node 10")
            cmds.append(f" if-match ip-prefix {prefixes_ipv4[0]}")  # Apenas o primeiro prefixo IPv4
            cmds.append(" quit")

            # Configuração do export IPv4: permite todos os prefixos
            cmds.append(f"route-policy {route_policy_export_ipv4} permit node 10")
            cmds.append(" quit")

            # Configuração do import IPv6: permite apenas os prefixos definidos
            cmds.append(f"route-policy {route_policy_import_ipv6} permit node 10")
            cmds.append(f" if-match ipv6-prefix {prefixes_ipv6[0]}")  # Apenas o primeiro prefixo IPv6
            cmds.append(" quit")

            # Configuração do export IPv6: permite todos os prefixos
            cmds.append(f"route-policy {route_policy_export_ipv6} permit node 10")
            cmds.append(" quit")

            # Configuração do BGP
            cmds.append(f"bgp {local_as}")
            cmds.append(f" peer {neighbor_ip} as-number {neighbor_as}")
            cmds.append(" ipv4-family unicast")
            cmds.append(f"  peer {neighbor_ip} enable")
            cmds.append(f"  peer {neighbor_ip} route-policy {route_policy_import_ipv4} import")  # Importar prefixos IPv4
            cmds.append(f"  peer {neighbor_ip} route-policy {route_policy_export_ipv4} export")  # Exportar todos os prefixos IPv4

            cmds.append(" ipv6-family unicast")
            cmds.append(f"  peer {neighbor_ip} enable")
            cmds.append(f"  peer {neighbor_ip} route-policy {route_policy_import_ipv6} import")  # Importar prefixos IPv6
            cmds.append(f"  peer {neighbor_ip} route-policy {route_policy_export_ipv6} export")  # Exportar todos os prefixos IPv6
            cmds.append(" quit")

            # Aplicar configurações no roteador
            for cmd in cmds:
                conn.send_command(cmd)

            status_out = conn.send_command(f"display bgp peer {neighbor_ip}")
            status = "SUCESSO" if "Established" in status_out else "BGP NÃO ESTABELECIDO"
            logger.info(f"Status BGP para {r['host']}: {status}")
            conn.disconnect()

            resultados.append({"host": r['host'], "status": status, "tempo": time.time()})
        except Exception as e:
            logger.error(f"Erro ao conectar ou configurar {r['host']}: {e}")

    return resultados

# ================= RELATÓRIO EM PDF =================

def gerar_relatorio(resultados):
    doc = SimpleDocTemplate("relatorio_huawei.pdf", pagesize=A4)
    styles = getSampleStyleSheet()
    elems = []

    elems.append(Paragraph("Relatório Automação BGP Huawei", styles['Title']))
    elems.append(Paragraph(f"Empresa: {EMPRESA}", styles['Normal']))
    elems.append(Paragraph(datetime.now().strftime('%d/%m/%Y %H:%M'), styles['Normal']))
    elems.append(Spacer(1, 12))

    tabela = [["Roteador", "Status", "Tempo (s)"]]
    for r in resultados:
        tabela.append([r['host'], r['status'], r['tempo']])

    t = Table(tabela)
    t.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 1, colors.black),
                           ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey)]))

    elems.append(t)
    doc.build(elems)
    logger.info("Relatório gerado: relatorio_huawei.pdf")

# ================= FUNÇÃO PRINCIPAL =================

def main():
    LOCAL_AS = obter_as_local()
    NEIGHBOR_IP = obter_ip_neigh()
    NEIGHBOR_AS = obter_as_neigh()
    PREFIX_NAME = obter_nome_cliente()  # Nome do cliente para gerar prefixos e políticas

    # Obter os prefixos IPv4 e IPv6 do usuário
    adicionar_prefixos_ipv4()  # Prefixos IPv4
    adicionar_prefixos_ipv6()  # Prefixos IPv6

    # Gerar prefixos e policies automaticamente
    nome_prefix_ipv4, ROUTE_POLICY_IMPORT_IPV4, ROUTE_POLICY_EXPORT_IPV4, nome_prefix_ipv6, ROUTE_POLICY_IMPORT_IPV6, ROUTE_POLICY_EXPORT_IPV6 = gerar_policies_e_prefixos(PREFIX_NAME)

    # Confirmação
    confirmacao(LOCAL_AS, NEIGHBOR_IP, NEIGHBOR_AS, PREFIX_NAME, prefixes_ipv4, prefixes_ipv6, ROUTE_POLICY_IMPORT_IPV4, ROUTE_POLICY_EXPORT_IPV4, ROUTE_POLICY_IMPORT_IPV6, ROUTE_POLICY_EXPORT_IPV6)

    # Conexão e execução
    routers_all = ler_routers_txt()
    routers = escolher_roteadores(routers_all)
    resultados = executar_bgp(routers, LOCAL_AS, NEIGHBOR_IP, NEIGHBOR_AS, prefixes_ipv4, ROUTE_POLICY_IMPORT_IPV4, ROUTE_POLICY_EXPORT_IPV4, prefixes_ipv6, ROUTE_POLICY_IMPORT_IPV6, ROUTE_POLICY_EXPORT_IPV6)

    # Gerar relatório PDF
    gerar_relatorio(resultados)

if __name__ == "__main__":
    main()
