import { useEffect, useState } from "react";
import api from "../api/client";
import styles from "./Page.module.css";

export default function Roteadores() {
  const [routers, setRouters] = useState([]);
  const [form, setForm] = useState({ host: "", username: "", password: "", port: "22" });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(null);

  async function load() {
    try {
      const { data } = await api.get("/roteadores");
      setRouters(data);
    } catch {
      setError("Erro ao carregar roteadores.");
    }
  }

  useEffect(() => { load(); }, []);

  function handleChange(e) {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));
  }

  async function handleDelete(host) {
    if (!window.confirm(`Remover o roteador "${host}"?`)) return;
    setDeleting(host);
    setError("");
    try {
      await api.delete(`/roteadores/${encodeURIComponent(host)}`);
      await load();
    } catch (err) {
      setError(err.response?.data?.detail ?? "Erro ao remover roteador.");
    } finally {
      setDeleting(null);
    }
  }

  async function handleAdd(e) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      await api.post("/roteadores", { ...form, port: Number(form.port) });
      setForm({ host: "", username: "", password: "", port: "22" });
      await load();
    } catch (err) {
      setError(err.response?.data?.detail ?? "Erro ao adicionar roteador.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <h2 className={styles.pageTitle}>Roteadores</h2>

      <div className={styles.card}>
        <h3 className={styles.cardTitle}>Inventário</h3>
        {routers.length === 0 ? (
          <p className={styles.muted}>Nenhum roteador cadastrado.</p>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Host</th>
                <th>Usuário</th>
                <th>Porta</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {routers.map((r) => (
                <tr key={r.host}>
                  <td>{r.host}</td>
                  <td>{r.username}</td>
                  <td>{r.port}</td>
                  <td>
                    <button
                      className={styles.btnDelete}
                      onClick={() => handleDelete(r.host)}
                      disabled={deleting === r.host}
                    >
                      {deleting === r.host ? "Removendo…" : "Excluir"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className={styles.card}>
        <h3 className={styles.cardTitle}>Adicionar Roteador</h3>
        {error && <p className={styles.error}>{error}</p>}
        <form className={styles.grid2} onSubmit={handleAdd}>
          <label className={styles.label}>
            Host / IP
            <input className={styles.input} name="host" value={form.host} onChange={handleChange} required />
          </label>
          <label className={styles.label}>
            Usuário SSH
            <input className={styles.input} name="username" value={form.username} onChange={handleChange} required />
          </label>
          <label className={styles.label}>
            Senha SSH
            <input className={styles.input} type="password" name="password" value={form.password} onChange={handleChange} required />
          </label>
          <label className={styles.label}>
            Porta
            <input className={styles.input} name="port" type="number" value={form.port} onChange={handleChange} required />
          </label>
          <button className={styles.btn} type="submit" disabled={saving} style={{ gridColumn: "1 / -1" }}>
            {saving ? "Salvando…" : "Adicionar"}
          </button>
        </form>
      </div>
    </div>
  );
}
