import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router";

import "./assets/styles/index.css";

import Login from "./pages/Login.jsx";
import StudentDashboard from "./pages/student/Dashboard.jsx";
import TeacherDashboard from "./pages/teacher/Dashboard.jsx";
import ObserverDashboard from "./pages/observer/Dashboard.jsx";
import AdminDashboard from "./pages/admin/Dashboard.jsx";
import Navbar from "./components/sides/Navbar.jsx";
import Aside from "./components/sides/Aside.jsx";

// Главная страница для каждой роли
const ROLE_HOME = {
  student: "/student",
  teacher: "/teacher",
  observer: "/observer",
  admin: "/admin",
};

const getToken = () =>
  localStorage.getItem("token") || sessionStorage.getItem("token");
  localStorage.getItem("token") || sessionStorage.getItem("token");

const getUser = () => {
  try {
    return JSON.parse(
      localStorage.getItem("user") || sessionStorage.getItem("user") || "null"
    );
  } catch {
    return null;
  }
};;

const isAuthenticated = () => !!getToken() && !!getUser();

const homeFor = (user) => ROLE_HOME[user?.role] || "/login";

// Защищённый маршрут: нужен вход и подходящая роль
function ProtectedRoute({ roles, children }) {
  const user = getUser();

  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  if (roles && !roles.includes(user.role)) {
    return <Navigate to={homeFor(user)} replace />;
  }
  return children;
}

function MainLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  if (!isAuthenticated()) return <Navigate to="/login" replace />;

  return (
    <div className="flex min-h-screen bg-[#f5f6f8]">
      <Aside mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Navbar onMenuClick={() => setMobileOpen(true)} />
        <main className="flex-1 p-3">
          <div className="bg-white p-3 rounded-2xl shadow-md">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}

// Страница для неавторизованных (логин)
function PublicRoute({ children }) {
  return isAuthenticated() ? (
    <Navigate to={homeFor(getUser())} replace />
  ) : (
    children
  );
}

// Редирект с "/" на раздел своей роли
function HomeRedirect() {
  return isAuthenticated() ? (
    <Navigate to={homeFor(getUser())} replace />
  ) : (
    <Navigate to="/login" replace />
  );
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={
            <PublicRoute>
              <Login />
            </PublicRoute>
          }
        />

        {/* Все страницы с Navbar */}
        <Route element={<MainLayout />}>
          <Route
            path="/student/*"
            element={
              <ProtectedRoute roles={["student"]}>
                <StudentDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/teacher/*"
            element={
              <ProtectedRoute roles={["teacher", "admin"]}>
                <TeacherDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/observer/*"
            element={
              <ProtectedRoute roles={["observer", "admin"]}>
                <ObserverDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/*"
            element={
              <ProtectedRoute roles={["admin"]}>
                <AdminDashboard />
              </ProtectedRoute>
            }
          />
        </Route>

        <Route path="/" element={<HomeRedirect />} />
        <Route path="*" element={<HomeRedirect />} />
      </Routes>
    </BrowserRouter>
  );
}

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
