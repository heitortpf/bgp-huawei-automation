import { useEffect, useState } from "react";
import api from "../api/client";
import styles from "./Page.module.css";
import { downloadBlob } from "../utils/download";

const EMPTY_FORM = {
  local_as: "",
  neighbor_ip: "",
  neighbor_as: "",
  nome_cliente: "",
};

function statusTag(status) {
  if (!status) return null;
  const s = status.toUpperCase();
  if (s.includes("SUCESSO") || s.includes("ESTABLISHED")) return <span className={styles.tagSuccess}>{status}</span>;
  if (s.includes("ERRO") || s.includes("NÃO")) return <span className={styles.tagError}>{status}</span>;
  return <span className={styles.tagWarn}>{status}</span>;
}

export default function CriarSessao() {
  const [form, setForm] = useState(EMPTY_FORM);
  const [prefixesV4, setPrefixesV4] = useState([""]);
  const [prefixesV6, setPrefixesV6] = useState([""]);
  const [routers, setRouters] = useState([]);
  const [selectedRouters, setSelectedRouters] = useState([]);
  const [aplicarSeExistir, setAplicarSeExistir] = useState(false);
  const [gerarRelatorio, setGerarRelatorio] = useState(true);

  const [loadingPrefixos, setLoadingPrefixos] = useState(false);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [loadingAplicar, setLoadingAplicar] = useState(false);

  const [preview, setPreview] = useState(null);
  const [resultados, setResultados] = useState(null);
  const [relatorioPdf, setRelatorioPdf] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/roteadores").then(({ data }) => {
      setRouters(data);
      setSelectedRouters(data.map((r) => r.host));
    });
  }, []);

  function handleChange(e) {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));
  }

  function buildSession() {
    return {
      local_as: Number(form.local_as),
      neighbor_ip: form.neighbor_ip,
      neighbor_as: Number(form.neighbor_as),
      nome_cliente: form.nome_cliente,
      prefixes_ipv4: prefixesV4.filter(Boolean),
      prefixes_ipv6: prefixesV6.filter(Boolean),
    };
  }

  async function handleBuscarPrefixos() {
    if (!form.neighbor_as) return;
    setError("");
    setLoadingPrefixos(true);
    try {
      const { data } = await api.get(`/sessao/asn/${form.neighbor_as}/prefixos`);
      if (data.ipv4.length) setPrefixesV4(data.ipv4);
      if (data.ipv6.length) setPrefixesV6(data.ipv6);
    } catch (err) {
      setError(err.response?.data?.detail ?? "Erro ao buscar prefixos.");
    } finally {
      setLoadingPrefixos(false);
    }
  }

  async function handlePreview() {
    setError("");
    setLoadingPreview(true);
    try {
      const { data } = await api.post("/sessao/preview", { sessao: buildSession() });
      setPreview(data.comandos);
    } catch (err) {
      setError(err.response?.data?.detail ?? "Erro ao gerar preview.");
    } finally {
      setLoadingPreview(false);
    }
  }

  async function handleAplicar() {
    setError("");
    setResultados(null);
    setRelatorioPdf(null);
    setLoadingAplicar(true);
    try {
      const { data } = await api.post("/sessao/aplicar", {
        sessao: buildSession(),
        roteadores: selectedRouters,
        aplicar_se_existir: aplicarSeExistir,
        gerar_relatorio: gerarRelatorio,
      });
      setResultados(data.resultados);
      if (data.relatorio_nome) {
        setRelatorioPdf(data.relatorio_nome);
      }
    } catch (err) {
      setError(err.response?.data?.detail ?? "Erro ao aplicar sessão.");
    } finally {
      setLoadingAplicar(false);
    }
  }

  async function handleDownloadPdf() {
    if (!relatorioPdf) return;
    const resp = await api.get(`/relatorios/${relatorioPdf}`, { responseType: "blob" });
    downloadBlob(resp.data, relatorioPdf);
  }

  function toggleRouter(host) {
    setSelectedRouters((prev) =>
      prev.includes(host) ? prev.filter((h) => h !== host) : [...prev, host]
    );
  }

  function updatePrefix(list, setList, i, val) {
    const next = [...list];
    next[i] = val;
    setList(next);
  }

  function removePrefix(list, setList, i) {
    setList(list.filter((_, idx) => idx !== i));
  }

  return (
    <div>
      <h2 className={styles.pageTitle}>Nova Sessão BGP</h2>
      {error && <p className={styles.error}>{error}</p>}

      {/* Dados da sessão */}
      <div className={styles.card}>
        <h3 className={styles.cardTitle}>Dados da Sessão</h3>
        <div className={styles.grid2}>
          <label className={styles.label}>
            AS Local
            <input className={styles.input} name="local_as" type="number" value={form.local_as} onChange={handleChange} placeholder="ex: 65001" />
          </label>
          <label className={styles.label}>
            IP do Vizinho
            <input className={styles.input} name="neighbor_ip" value={form.neighbor_ip} onChange={handleChange} placeholder="ex: 10.0.0.1" />
          </label>
          <label className={styles.label}>
            AS do Vizinho
            <input className={styles.input} name="neighbor_as" type="number" value={form.neighbor_as} onChange={handleChange} placeholder="ex: 28571" />
          </label>
          <label className={styles.label}>
            Nome do Cliente
            <input className={styles.input} name="nome_cliente" value={form.nome_cliente} onChange={handleChange} placeholder="ex: CLIENTE_XPTO" />
          </label>
        </div>
      </div>

      {/* Prefixos */}
      <div className={styles.card}>
        <div className={styles.cardHeader}>
          <h3 className={styles.cardTitle}>Prefixos</h3>
          <button className={styles.btnSecondary} onClick={handleBuscarPrefixos} disabled={!form.neighbor_as || loadingPrefixos}>
            {loadingPrefixos ? <><span className={styles.spinner} />Buscando…</> : "Buscar pelo AS"}
          </button>
        </div>

        <div className={styles.grid2}>
          <div>
            <p className={styles.muted} style={{ marginBottom: 8 }}>IPv4</p>
            <div className={styles.prefixList}>
              {prefixesV4.map((p, i) => (
                <div key={i} className={styles.prefixRow}>
                  <input className={styles.input} value={p} onChange={(e) => updatePrefix(prefixesV4, setPrefixesV4, i, e.target.value)} placeholder="200.0.0.0/20" />
                  {prefixesV4.length > 1 && (
                    <button className={styles.removeBtn} onClick={() => removePrefix(prefixesV4, setPrefixesV4, i)}>×</button>
                  )}
                </div>
              ))}
              <button className={styles.addPrefixBtn} onClick={() => setPrefixesV4([...prefixesV4, ""])}>+ Adicionar IPv4</button>
            </div>
          </div>
          <div>
            <p className={styles.muted} style={{ marginBottom: 8 }}>IPv6</p>
            <div className={styles.prefixList}>
              {prefixesV6.map((p, i) => (
                <div key={i} className={styles.prefixRow}>
                  <input className={styles.input} value={p} onChange={(e) => updatePrefix(prefixesV6, setPrefixesV6, i, e.target.value)} placeholder="2001:db8::/32" />
                  {prefixesV6.length > 1 && (
                    <button className={styles.removeBtn} onClick={() => removePrefix(prefixesV6, setPrefixesV6, i)}>×</button>
                  )}
                </div>
              ))}
              <button className={styles.addPrefixBtn} onClick={() => setPrefixesV6([...prefixesV6, ""])}>+ Adicionar IPv6</button>
            </div>
          </div>
        </div>
      </div>

      {/* Preview */}
      <div className={styles.card}>
        <div className={styles.cardHeader}>
          <h3 className={styles.cardTitle}>Preview de Comandos</h3>
          <button className={styles.btnSecondary} onClick={handlePreview} disabled={loadingPreview}>
            {loadingPreview ? <><span className={styles.spinner} />Gerando…</> : "Gerar Preview"}
          </button>
        </div>
        {preview && (
          <pre className={styles.codeBlock}>{preview.join("\n")}</pre>
        )}
      </div>

      {/* Roteadores + opções */}
      <div className={styles.card}>
        <h3 className={styles.cardTitle}>Roteadores</h3>
        {routers.length === 0 ? (
          <p className={styles.muted}>Nenhum roteador cadastrado.</p>
        ) : (
          <div className={styles.routerCheckboxes}>
            {routers.map((r) => (
              <label key={r.host}>
                <input type="checkbox" checked={selectedRouters.includes(r.host)} onChange={() => toggleRouter(r.host)} />
                {r.host} <span className={styles.muted}>({r.username}:{r.port})</span>
              </label>
            ))}
          </div>
        )}
        <div style={{ marginTop: 16, display: "flex", gap: 20, flexWrap: "wrap" }}>
          <label className={styles.toggle}>
            <input type="checkbox" checked={aplicarSeExistir} onChange={(e) => setAplicarSeExistir(e.target.checked)} />
            Aplicar se já existir
          </label>
          <label className={styles.toggle}>
            <input type="checkbox" checked={gerarRelatorio} onChange={(e) => setGerarRelatorio(e.target.checked)} />
            Gerar relatório PDF
          </label>
        </div>
      </div>

      {/* Ação principal */}
      <div className={styles.actions}>
        <button className={styles.btn} onClick={handleAplicar} disabled={loadingAplicar || selectedRouters.length === 0}>
          {loadingAplicar ? <><span className={styles.spinner} />Aplicando…</> : "Aplicar nos Roteadores"}
        </button>
        {relatorioPdf && (
          <button className={styles.btnSecondary} onClick={handleDownloadPdf}>
            Baixar PDF
          </button>
        )}
      </div>

      {/* Resultados */}
      {resultados && (
        <div className={styles.card} style={{ marginTop: 20 }}>
          <h3 className={styles.cardTitle}>Resultados</h3>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Roteador</th>
                <th>Status</th>
                <th>Duração</th>
                <th>Backup SHA256</th>
              </tr>
            </thead>
            <tbody>
              {resultados.map((r) => (
                <tr key={r.host}>
                  <td>{r.host}</td>
                  <td>{statusTag(r.status)}</td>
                  <td>{r.duracao_s.toFixed(1)}s</td>
                  <td style={{ fontFamily: "monospace", fontSize: 11 }}>{r.backup_sha256}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
