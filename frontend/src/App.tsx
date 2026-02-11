import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import JobList from "./components/JobList";
import JobDetailPage from "./components/JobDetail";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<JobList />} />
        <Route path="/jobs/:name" element={<JobDetailPage />} />
      </Routes>
    </Layout>
  );
}
