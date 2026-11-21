import { useState } from "react";
import { useNavigate } from "react-router";
import { Form, Input, Checkbox, Button, Alert, ConfigProvider } from "antd";
import gerb from "../assets/images/gerb.png";

const API_URL = "http://127.0.0.1:8000/api/auth";

const ROUTES = {
  student: "/student",
  teacher: "/teacher",
  observer: "/observer",
  admin: "/admin",
};
function Login() {
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const onFinish = async ({ student_id, password, remember }) => {
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/login/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ student_id, password }),
      });
      const data = await res.json();

      if (res.ok) {
        const storage = remember ? localStorage : sessionStorage;
        storage.setItem("token", data.token);
        storage.setItem("refresh", data.refresh);
        storage.setItem("user", JSON.stringify(data.user));
        navigate(ROUTES[data.user.role] || "/", { replace: true });
      } else {
        setError(
          data.message ||
            data.student_id?.[0] ||
            data.password?.[0] ||
            "Ошибка входа",
        );
      }
    } catch (err) {
      console.error(err);
      setError("Server mavjud emas");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="min-h-screen w-full flex flex-col bg-linear-to-br from-[#f4f3f3] via-[#f2e9e4] to-[#f1e0eb] font-[Arial,sans-serif]">
        {/* Верхний логотип */}
        <header className="absolute top-0 left-0 px-8 py-7">
          <div className="flex items-center gap-2 text-[27px] font-bold text-[#171717]">
            <span className="text-3xl">ϟ</span>
            <span>unioes</span>
          </div>
        </header>

        {/* Центральная часть */}
        <main className="flex flex-1 items-center justify-center px-5 py-24">
          {/* Карточка авторизации */}
          <div className="w-full max-w-105 rounded-[27px] bg-white px-10 py-9 shadow-[0_5px_25px_rgba(0,0,0,0.025)]">
            {/* Эмблема университета */}
            <div className="flex flex-col items-center mb-7">
              <img
                src={gerb}
                alt="Cyber University emblem"
                className="w-31.25 h-31.25 object-contain mb-3"
              />

              <h1 className="text-center text-[21px] leading-7 font-bold text-[#111111]">
                Государственный университет “Cyber university” 
              </h1>
            </div>

            {/* Форма входа */}
            <ConfigProvider
              theme={{
                token: {
                  borderRadius: 10,
                  controlHeight: 47,
                  fontSize: 16,
                },
              }}
            >
              <Form
                layout="vertical"
                onFinish={onFinish}
                initialValues={{ remember: false }}
                requiredMark={false}
                size="large"
              >
                <h1 className="mb-2 text-[16px] leading-7 text-[#111111]">
                  ID
                </h1>
                <Form.Item
                  name="student_id"
                  normalize={(value) => (value || "").replace(/\D/g, "")}
                  rules={[
                    { required: true, message: "Введите ID" },
                    {
                      pattern: /^\d{12}$/,
                      message:
                        "ID должен состоять из 12 цифр.",
                    },
                  ]}
                >
                  <Input
                    inputMode="numeric"
                    maxLength={12}
                    placeholder="ID"
                  />
                </Form.Item>
                <h1 className="mb-2 text-[16px] leading-7 text-[#111111]">
                  Пароль
                </h1>
                <Form.Item
                  name="password"
                  rules={[{ required: true, message: "Введите пароль" }]}
                >
                  <Input.Password placeholder="Введите пароль" />
                </Form.Item>

                <Form.Item name="remember" valuePropName="checked">
                  <Checkbox>Запомнить меня</Checkbox>
                </Form.Item>

                {error && (
                  <Alert
                    type="error"
                    title={error}
                    showIcon
                    closable
                    onClose={() => setError("")}
                    style={{ marginBottom: 16 }}
                  />
                )}

                <Form.Item style={{ marginBottom: 0 }}>
                  <Button
                    type="primary"
                    htmlType="submit"
                    loading={loading}
                    block
                    shape="round"
                    style={{ height: 49, fontWeight: 500 }}
                  >
                    {loading ? "Вводится..." : "Войти"}
                  </Button>
                </Form.Item>
              </Form>
            </ConfigProvider>
          </div>
        </main>

        {/* Нижняя часть */}
        <footer className="text-center pb-5 text-sm text-[#858585]">
          © 2026 UNIOES
        </footer>
      </div>
    </>
  );
}

export default Login;
