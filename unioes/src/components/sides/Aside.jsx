import { useState } from "react";
import { useLocation, useNavigate } from "react-router";
import { Layout, Menu, ConfigProvider } from "antd";
import {
  DashboardOutlined,
  FileTextOutlined,
  TrophyOutlined,
  MailOutlined,
  UserOutlined,
  TeamOutlined,
  EyeOutlined,
  LogoutOutlined,
  HomeOutlined,
} from "@ant-design/icons";

const { Sider } = Layout;

const MENU = {
  student: [
    { to: "/student/dashboard", label: "Главная", icon: <HomeOutlined /> },
    {
      to: "/student/exams",
      label: "Доступные экзамены",
      icon: <FileTextOutlined />,
    },
    {
      to: "/student/results",
      label: "Мои Результаты",
      icon: <TrophyOutlined />,
    },
    { to: "/student/appeals", label: "Мои Аппеляции", icon: <MailOutlined /> },
    { to: "/student/profile", label: "Профиль", icon: <UserOutlined /> },
  ],
  teacher: [
    { to: "/teacher/dashboard", label: "Главная", icon: <HomeOutlined /> },
    { to: "/teacher/exams", label: "Мои экзамены", icon: <FileTextOutlined /> },
  ],
  observer: [{ to: "/observer", label: "Главная", icon: <EyeOutlined /> }],
  admin: [
    { to: "/admin/dashboard", label: "Главная", icon: <HomeOutlined /> },
    { to: "/admin/users", label: "Пользователи", icon: <TeamOutlined /> },
  ],
};

const getUser = () => {
  try {
    return JSON.parse(
      localStorage.getItem("user") || sessionStorage.getItem("user") || "null",
    );
  } catch {
    return null;
  }
};

export default function Aside() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const user = getUser();
  const links = MENU[user?.role] || [];

  // Активный пункт: самый длинный путь, с которого начинается текущий URL
  const selected = links
    .filter((l) => pathname === l.to || pathname.startsWith(l.to + "/"))
    .sort((a, b) => b.to.length - a.to.length)[0]?.to;

  const items = [
    ...links.map(({ to, label, icon }) => ({ key: to, label, icon })),
    { type: "divider" },
    { key: "logout", label: "Выйти", icon: <LogoutOutlined />, danger: true },
  ];

  const logout = () => {
    ["token", "user"].forEach((k) => {
      localStorage.removeItem(k);
      sessionStorage.removeItem(k);
    });
    navigate("/login", { replace: true });
  };

  const onClick = ({ key }) => (key === "logout" ? logout() : navigate(key));

  return (
    <div className="bg-white">
      <ConfigProvider
        theme={{
          token: { borderRadius: 10 },
          components: {
            Menu: {
              // itemSelectedBg: "#91e568",
              itemSelectedColor: "#111111",
              itemHoverBg: "#f1f9ec",
              itemHeight: 46,
              itemMarginInline: 10,
            },
            Layout: { siderBg: "#ffffff" },
          },
        }}
      >
        <Sider
          theme="light"
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          width={250}
          style={{
            position: "sticky",
            top: 0,
            height: "100vh",
            overflow: "auto",
            borderRight: "1px solid #eee",
          }}
        >
          {/* Логотип */}
          <div className="flex items-center gap-2 px-6 py-5 text-[22px] font-bold text-[#171717] whitespace-nowrap overflow-hidden">
            <span className="text-2xl">ϟ</span>
            {!collapsed && <span>unioes</span>}
            <div className="capitalize">{user?.role}</div>
          </div>

          <Menu
            mode="inline"
            items={items}
            selectedKeys={selected ? [selected] : []}
            onClick={onClick}
            style={{ borderInlineEnd: "none" }}
          />
        </Sider>
      </ConfigProvider>
    </div>
  );
}
