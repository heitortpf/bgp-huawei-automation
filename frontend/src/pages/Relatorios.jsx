import { useEffect, useState } from "react";
import api from "../api/client";
import styles from "./Page.module.css";
import { downloadBlob } from "../utils/download";

export default function Relatorios() {
  const [files, setFiles] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get("/relatorios")
      .then(({ data }) => setFiles(data))
      .catch(() => setError("Não foi possível listar relatórios."));
  }, []);

  async function handleDownload(nome) {
    try {
      const resp = await api.get(`/relatorios/${nome}`, { responseType: "blob" });
      downloadBlob(resp.data, nome);
    } catch {
      setError(`Erro ao baixar ${nome}.`);
    }
  }

  return (
    <div>
      <h2 className={styles.pageTitle}>Relatórios</h2>
      <div className={styles.card}>
        {error && <p className={styles.error}>{error}</p>}
        {files.length === 0 && !error ? (
          <p className={styles.muted}>Nenhum relatório gerado ainda.</p>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Arquivo</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {files.map((f) => (
                <tr key={f}>
                  <td>{f}</td>
                  <td>
                    <button className={styles.btnSm} onClick={() => handleDownload(f)}>
                      Baixar PDF
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
