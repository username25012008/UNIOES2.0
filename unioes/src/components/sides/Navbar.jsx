import { useLocation, useNavigate } from "react-router";
import { Layout, Avatar, Badge, Button, Dropdown, Space, Typography, ConfigProvider } from "antd";
import {
  BellOutlined,
  UserOutlined,
  LogoutOutlined,
  MenuOutlined,
  DownOutlined,
} from "@ant-design/icons";

const { Header } = Layout;
const { Text } = Typography;

// Заголовок страницы по текущему пути
const TITLES = {
  exams: "Доступные экзамены",
  results: "Результаты",
  appeals: "Аппеляции",
  profile: "Профиль",
  users: "Пользователи",
};

const getUser = () => {
  try {
    return JSON.parse(
      localStorage.getItem("user") || sessionStorage.getItem("user") || "null"
    );
  } catch {
    return null;
  }
};

export default function Navbar({ onMenuClick }) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const user = getUser();

  const last = pathname.split("/").filter(Boolean).pop();
  const title = TITLES[last] || "Главная";

  const logout = () => {
    ["token", "user"].forEach((k) => {
      localStorage.removeItem(k);
      sessionStorage.removeItem(k);
    });
    navigate("/login", { replace: true });
  };

  const menu = {
    items: [
      {
        key: "profile",
        icon: <UserOutlined />,
        label: "Profile",
        onClick: () => navigate(`/${user?.role || "student"}/profile`),
      },
      { type: "divider" },
      {
        key: "logout",
        icon: <LogoutOutlined />,
        label: "Выйти",
        danger: true,
        onClick: logout,
      },
    ],
  };

  return (
    <ConfigProvider
      theme={{
        token: { colorPrimary: "#91e568", borderRadius: 10},
        components: { Layout: { headerBg: "#ffffff", headerPadding: "0 16px" } },
      }}
    >
      <Header
        style={{
          position: "sticky",
          top: 0,
          zIndex: 50,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          height: 64,
          margin: 12,
          borderRadius: 16,
          background: "#fff",
          boxShadow: "0 4px 3px rgba(0,0,0,0.06)",
        }}
      >
        {/* Слева: кнопка меню (мобильные) и заголовок */}
        <Space size="middle">
          <Button
            type="text"
            icon={<MenuOutlined />}
            onClick={onMenuClick}
            className="md:hidden!"
            aria-label="Open menu"
          />
          <Text strong style={{ fontSize: 18 }}>
            {title}
          </Text>
        </Space>

        {/* Справа: уведомления и профиль */}
        <div className="mr-3">
            <Space size="middle">
          <Badge count={Number(user?.notificationCount) || 0} size="small">
            <Button type="text" shape="circle" icon={<BellOutlined style={{ fontSize: 18 }} />} />
          </Badge>

          <Dropdown menu={menu} trigger={["click"]} placement="bottomRight">
            <Space style={{ cursor: "pointer" }}>
              <Avatar src={user?.image} icon={<UserOutlined />} />
              <div className="hidden sm:block" style={{ lineHeight: 1.2 }}>
                <div style={{ fontWeight: 600, fontSize: 14 }}>
                  {user?.shortName || user?.fullName}
                </div>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {user?.eduGroup}
                </Text>
              </div>
              <DownOutlined style={{ fontSize: 10, color: "#999" }} />
            </Space>
          </Dropdown>
        </Space>
        </div>
      </Header>
    </ConfigProvider>
  );
}