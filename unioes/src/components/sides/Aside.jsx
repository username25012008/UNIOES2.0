import { useState } from "react";
  import { logout as logoutSession } from "../../api/client.js";
  import { useLocation, useNavigate } from "react-router";
  import { Layout, Menu, ConfigProvider } from "antd";
  import { MENU, activeItem } from "./Menu.jsx";
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
    EditOutlined,
  } from "@ant-design/icons";

  const { Sider } = Layout;

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
    const selected = activeItem(user?.role, pathname)?.to;

    const items = [
      ...links.map(({ to, label, icon }) => ({ key: to, label, icon })),
      { type: "divider" },
      { key: "logout", label: "Выйти", icon: <LogoutOutlined />, danger: true },
    ];

    const logout = () => {
      logoutSession().finally(() => navigate("/login", { replace: true }));
    };

    const onClick = ({ key }) => (key === "logout" ? logout() : navigate(key));

    return (
      <div className="bg-white">
        <ConfigProvider
          theme={{
            token: { borderRadius: 10 },
            components: {
              Menu: {
                itemSelectedColor: "#111111",
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
              {!collapsed && <><span>unioes</span><span className="capitalize">{user?.role}</span></>}
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
