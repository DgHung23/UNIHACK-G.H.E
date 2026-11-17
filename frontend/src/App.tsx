import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Batches from "./pages/Batches";
import BatchDetail from "./pages/BatchDetail";
import NewBatch from "./pages/NewBatch";
import Alerts from "./pages/Alerts";
import Ledger from "./pages/Ledger";
import Trace from "./pages/Trace";
import Admin from "./pages/Admin";
import Settings from "./pages/Settings";
import type { ReactNode } from "react";

function Protected({ children, roles }: { children: ReactNode; roles?: string[] }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) return <div className="p-8 text-slate-500">Bạn không có quyền xem trang này.</div>;
  return <Layout>{children}</Layout>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/trace/:batchId" element={<Trace />} />
      <Route path="/" element={<Protected><Dashboard /></Protected>} />
      <Route path="/batches" element={<Protected><Batches /></Protected>} />
      <Route path="/batches/new" element={<Protected roles={["FARMER", "ADMIN"]}><NewBatch /></Protected>} />
      <Route path="/batches/:id" element={<Protected><BatchDetail /></Protected>} />
      <Route path="/alerts" element={<Protected><Alerts /></Protected>} />
      <Route path="/ledger" element={<Protected><Ledger /></Protected>} />
      <Route path="/admin" element={<Protected roles={["ADMIN"]}><Admin /></Protected>} />
      <Route path="/settings" element={<Protected roles={["ADMIN"]}><Settings /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
