import "./App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { useAuth } from "./lib/useAuth";
import Login from "./pages/Login";
import Layout from "./components/Layout";
import Chat from "./pages/Chat";
import DataFiles from "./pages/DataFiles";
import Sync from "./pages/Sync";
import Privacy from "./pages/Privacy";

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-zinc-500" data-testid="auth-loading">
        Loading…
      </div>
    );
  }
  if (!user) return <Navigate to="/" replace />;
  return children;
}

function App() {
  return (
    <div className="App">
      <Toaster position="top-right" richColors closeButton />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Login />} />
          <Route
            path="/app"
            element={
              <Protected>
                <Layout />
              </Protected>
            }
          >
            <Route index element={<Navigate to="chat" replace />} />
            <Route path="chat" element={<Chat />} />
            <Route path="data" element={<DataFiles />} />
            <Route path="sync" element={<Sync />} />
            <Route path="privacy" element={<Privacy />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;