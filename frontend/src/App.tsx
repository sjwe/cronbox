import { Routes, Route, Outlet } from "react-router-dom";
import Login from "./components/Login";
import ProtectedRoute from "./components/ProtectedRoute";
import Layout from "./components/Layout";
import JobList from "./components/JobList";
import JobDetailPage from "./components/JobDetail";
import Settings from "./components/Settings";
import AdminUsers from "./components/AdminUsers";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <ProtectedRoute>
            <Layout>
              <Outlet />
            </Layout>
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<JobList />} />
        <Route path="/jobs/:name" element={<JobDetailPage />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/admin/users" element={<AdminUsers />} />
      </Route>
    </Routes>
  );
}
