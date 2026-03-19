import { Navigate, Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";
import NdviPage from "./pages/NdviPage";
import NotFoundPage from "./pages/NotFoundPage";
import RainfallPage from "./pages/RainfallPage";
import RegisterPage from "./pages/RegisterPage";
import TemperaturePage from "./pages/TemperaturePage";
import TvdiPage from "./pages/TvdiPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<HomePage />} />
        <Route path="rainfall" element={<RainfallPage />} />
        <Route path="temperature" element={<TemperaturePage />} />
        <Route path="ndvi" element={<NdviPage />} />
        <Route path="tvdi" element={<TvdiPage />} />
      </Route>
      <Route path="/404" element={<NotFoundPage />} />
      <Route path="*" element={<Navigate to="/404" replace />} />
    </Routes>
  );
}
