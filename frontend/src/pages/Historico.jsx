import { useEffect, useState } from "react";
import api from "../api/client";
import styles from "./Page.module.css";
import { downloadBlob } from "../utils/download";

function statusResumo(resultados) {
  if (!resultados?.length) return "-";
  const ok = resultados.filter((r) => r.status?.includes("SUCESSO")).length;
  return `${ok}/${resultados.length} OK`;
}

export default function Historico() {
  const [historico, setHistorico] = useState([]);
  const [expandido, setExpandido] = useState(new Set());
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get("/historico")
      .then(({ data }) => setHistorico(data))
      .catch(() => setError("Não foi possível carregar o histórico."));
  }, []);

  function toggleExpandir(id) {
    setExpandido((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  async function handleDownload(nome) {
    try {
      const resp = await api.get(`/relatorios/${nome}`, { responseType: "blob" });
      downloadBlob(resp.data, nome);
    } catch {
      setError(`Erro ao baixar ${nome}.`);
    }
  }

  function formatTs(ts) {
    try {
      return new Date(ts).toLocaleString("pt-BR");
    } catch {
      return ts;
    }
  }

  return (
    <div>
      <h2 className={styles.pageTitle}>Histórico de Sessões</h2>
      {error && <p className={styles.error}>{error}</p>}
      <div className={styles.card}>
        {historico.length === 0 && !error ? (
          <p className={styles.muted}>Nenhuma sessão aplicada ainda.</p>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Data/Hora</th>
                <th>Cliente</th>
                <th>Vizinho</th>
                <th>Roteadores</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {historico.map((s) => (
                <>
                  <tr key={s.id} style={{ cursor: "pointer" }} onClick={() => toggleExpandir(s.id)}>
                    <td>{formatTs(s.timestamp)}</td>
                    <td>{s.nome_cliente}</td>
                    <td>
                      <span className={styles.muted}>AS{s.neighbor_as}</span> {s.neighbor_ip}
                    </td>
                    <td>{s.roteadores.join(", ")}</td>
                    <td>{statusResumo(s.resultados)}</td>
                    <td>
                      <span className={styles.muted}>{expandido.has(s.id) ? "▲" : "▼"}</span>
                    </td>
                  </tr>
                  {expandido.has(s.id) && (
                    <tr key={`${s.id}-detail`}>
                      <td colSpan={6} style={{ padding: "0 0 12px 24px" }}>
                        <table className={styles.table} style={{ marginTop: 8 }}>
                          <thead>
                            <tr>
                              <th>Roteador</th>
                              <th>Status</th>
                              <th>Duração</th>
                              <th>Backup SHA256</th>
                            </tr>
                          </thead>
                          <tbody>
                            {s.resultados.map((r) => (
                              <tr key={r.host}>
                                <td>{r.host}</td>
                                <td>{r.status}</td>
                                <td>{r.duracao_s?.toFixed(1)}s</td>
                                <td style={{ fontFamily: "monospace", fontSize: 11 }}>
                                  {r.backup_sha256}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {s.relatorio_nome && (
                          <button
                            className={styles.btnSm}
                            style={{ marginTop: 10 }}
                            onClick={() => handleDownload(s.relatorio_nome)}
                          >
                            Baixar PDF
                          </button>
                        )}
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
