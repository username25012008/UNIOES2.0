import { App, Button, Card, Form, Input } from "antd";
import { api, logout, passwordRules, PASSWORD_HINT } from "../api/client.js";

const ROLE = { student: "Студент", teacher: "Преподаватель", observer: "Наблюдатель", admin: "Администратор" };

export default function Profile() {
  return (
    <App>
      <ProfileInner />
    </App>
  );
}

function ProfileInner() {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const user = JSON.parse(localStorage.getItem("user") || sessionStorage.getItem("user") || "{}");
  const submit = async (v) => {
    try {
      await api("/auth/change-password/", { method: "POST", body: { old_password: v.old_password, new_password: v.new_password } });
      message.success("Пароль изменён. Войдите заново");
      form.resetFields();
      await logout(); // сервер отозвал старые токены
      window.location.href = "/login";
    } catch (e) { message.error(e.message); }
  };
  return (
    <div className="mx-auto max-w-xl space-y-4">
      <h1 className="text-xl font-semibold">Профиль</h1>
      <Card size="small">
        <p><b>{user.full_name}</b></p>
        <p className="text-gray-500">{ROLE[user.role]} · ID {user.student_id}{user.edu_group ? ` · ${user.edu_group}` : ""}</p>
      </Card>
      <Card size="small" title="Смена пароля">
        <Form form={form} layout="vertical" onFinish={submit}>
          <Form.Item name="old_password" label="Текущий пароль" rules={[{ required: true }]}><Input.Password autoComplete="current-password" /></Form.Item>
          <Form.Item name="new_password" label="Новый пароль" rules={passwordRules} extra={PASSWORD_HINT}><Input.Password autoComplete="new-password" /></Form.Item>
          <Form.Item name="confirm" label="Повторите пароль" dependencies={["new_password"]}
            rules={[{ required: true }, ({ getFieldValue }) => ({ validator: (_, v) => (!v || v === getFieldValue("new_password") ? Promise.resolve() : Promise.reject(new Error("Пароли не совпадают"))) })]}>
            <Input.Password autoComplete="new-password" /></Form.Item>
          <Button type="primary" htmlType="submit">Сменить пароль</Button>
        </Form>
      </Card>
    </div>
  );
}
