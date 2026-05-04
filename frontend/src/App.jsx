import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import PrivateRoute from "./components/PrivateRoute";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import CriarSessao from "./pages/CriarSessao";
import Roteadores from "./pages/Roteadores";
import Relatorios from "./pages/Relatorios";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <PrivateRoute>
                <Layout>
                  <CriarSessao />
                </Layout>
              </PrivateRoute>
            }
          />
          <Route
            path="/roteadores"
            element={
              <PrivateRoute>
                <Layout>
                  <Roteadores />
                </Layout>
              </PrivateRoute>
            }
          />
          <Route
            path="/relatorios"
            element={
              <PrivateRoute>
                <Layout>
                  <Relatorios />
                </Layout>
              </PrivateRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
