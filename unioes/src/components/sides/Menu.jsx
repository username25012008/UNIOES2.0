import {
  FileTextOutlined, TrophyOutlined, MailOutlined, UserOutlined,
  TeamOutlined, EyeOutlined, HomeOutlined, EditOutlined,
} from "@ant-design/icons";

export const MENU = {
  student: [
    { to: "/student/dashboard", label: "Главная", icon: <HomeOutlined /> },
    { to: "/student/exams", label: "Доступные экзамены", icon: <FileTextOutlined /> },
    { to: "/student/results", label: "Мои Результаты", icon: <TrophyOutlined /> },
    { to: "/student/appeals", label: "Мои Аппеляции", icon: <MailOutlined /> },
    { to: "/student/profile", label: "Профиль", icon: <UserOutlined /> },
  ],
  teacher: [
    { to: "/teacher/dashboard", label: "Главная", icon: <HomeOutlined /> },
    { to: "/teacher/exams", label: "Мои экзамены", icon: <FileTextOutlined /> },
    { to: "/teacher/grading", label: "Письменные работы", icon: <EditOutlined /> },
    { to: "/teacher/results", label: "Результаты", icon: <TrophyOutlined /> },
    { to: "/teacher/appeals", label: "Апелляции", icon: <MailOutlined /> },
  ],
  observer: [{ to: "/observer", label: "Главная", icon: <EyeOutlined /> }],
  admin: [
    { to: "/admin/dashboard", label: "Главная", icon: <HomeOutlined /> },
    { to: "/admin/users", label: "Пользователи", icon: <TeamOutlined /> },
    { to: "/admin/teaching", label: "Преподавание", icon: <FileTextOutlined /> },
    { to: "/admin/requests", label: "Запросы на удаление", icon: <MailOutlined /> },
    { to: "/admin/audit", label: "Журнал действий", icon: <EyeOutlined /> },
    { to: "/admin/appeals", label: "Апелляции", icon: <MailOutlined /> }
  ],
};

// Пункт меню, соответствующий текущему URL (самый длинный совпавший путь)
export const activeItem = (role, pathname) =>
  (MENU[role] || [])
    .filter((l) => pathname === l.to || pathname.startsWith(l.to + "/"))
    .sort((a, b) => b.to.length - a.to.length)[0];

// Страницы, которых нет в боковом меню
const EXTRA = { profile: "Профиль" };

export const pageTitle = (role, pathname) =>
  activeItem(role, pathname)?.label ||
  EXTRA[pathname.split("/").filter(Boolean).pop()] ||
  "Главная";