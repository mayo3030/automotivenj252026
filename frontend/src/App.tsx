import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Scrape from "./pages/Scrape";
import Inventory from "./pages/Inventory";
import VehicleDetail from "./pages/VehicleDetail";
import ApiDocs from "./pages/ApiDocs";
import Logs from "./pages/Logs";
import History from "./pages/History";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/scrape" element={<Scrape />} />
        <Route path="/history" element={<History />} />
        <Route path="/logs" element={<Logs />} />
        <Route path="/inventory" element={<Inventory />} />
        <Route path="/inventory/:vin" element={<VehicleDetail />} />
        <Route path="/api-docs" element={<ApiDocs />} />
      </Route>
    </Routes>
  );
}
