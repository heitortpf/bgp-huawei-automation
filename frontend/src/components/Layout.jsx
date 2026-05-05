import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import styles from "./Layout.module.css";

export default function Layout({ children }) {
  const { logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    <div className={styles.shell}>
      <nav className={styles.nav}>
        <span className={styles.brand}>BGP Huawei</span>
        <div className={styles.links}>
          <NavLink to="/" end className={({ isActive }) => (isActive ? styles.active : "")}>
            Nova Sessão
          </NavLink>
          <NavLink
            to="/roteadores"
            className={({ isActive }) => (isActive ? styles.active : "")}
          >
            Roteadores
          </NavLink>
          <NavLink
            to="/historico"
            className={({ isActive }) => (isActive ? styles.active : "")}
          >
            Histórico
          </NavLink>
          <NavLink
            to="/relatorios"
            className={({ isActive }) => (isActive ? styles.active : "")}
          >
            Relatórios
          </NavLink>
        </div>
        <button onClick={handleLogout} className={styles.logout}>
          Sair
        </button>
      </nav>
      <main className={styles.main}>{children}</main>
    </div>
  );
}
