import { useCallback, useEffect, useState } from "react";
import Profile from "../Profile.jsx";
import { Navigate, Route, Routes } from "react-router";
import { App as AntApp, Button, Card, Empty, Form, Input, Modal, Popconfirm, Select, Spin, Switch, Table, Tag } from "antd";
import { api, passwordRules, PASSWORD_HINT } from "../../api/client.js";
import { fmtDate } from "../../components/common/constants.js";
import AppealCard from "../../components/common/AppealCard.jsx";
import { APPEAL_STATUS } from "../../components/common/constants.js";

const ROLE = { student: "Студент", teacher: "Преподаватель", observer: "Наблюдатель", admin: "Администратор" };

function useList(path) {
  const { message } = AntApp.useApp();
  const [rows, setRows] = useState(null);
  const load = useCallback(() => api(path).then(setRows).catch((e) => { message.error(e.message); setRows([]); }), [path, message]);
  useEffect(() => { load(); }, [load]);
  return [rows, load];
}
const opts = (rows, label = "name") => (rows || []).map((r) => ({ value: r.id, label: r[label] }));

/* Пользователи: создание, группа студента, активация */
function Users() {
  const { message } = AntApp.useApp();
  const [role, setRole] = useState("");
  const [rows, load] = useList(`/admin/users/${role ? `?role=${role}` : ""}`);
  const [groups] = useList("/admin/groups/");
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();
  const [editForm] = Form.useForm();
  const [pwForm] = Form.useForm();
  const [edit, setEdit] = useState(null);
  const [pwUser, setPwUser] = useState(null);
  const r = Form.useWatch("role", form);
  const saveEdit = async (v) => { try { await api(`/admin/users/${edit.id}/`, { method: "PATCH", body: v }); message.success("Сохранено"); setEdit(null); load(); } catch (e) { message.error(e.message); } };
  const resetPw = async (v) => { try { await api(`/admin/users/${pwUser.id}/reset-password/`, { method: "POST", body: v }); message.success("Пароль сброшен"); setPwUser(null); pwForm.resetFields(); } catch (e) { message.error(e.message); } };

  const patch = async (u, body) => { try { await api(`/admin/users/${u.id}/`, { method: "PATCH", body }); load(); } catch (e) { message.error(e.message); } };
  const create = async (v) => {
    try { await api("/admin/users/", { method: "POST", body: v }); message.success("Пользователь создан"); setOpen(false); form.resetFields(); load(); }
    catch (e) { message.error(e.message); }
  };
  if (!rows) return <Spin />;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold">Пользователи</h1>
        <div className="flex gap-2">
          <Select allowClear placeholder="Все роли" style={{ width: 180 }} onChange={(v) => setRole(v || "")} options={Object.entries(ROLE).map(([value, label]) => ({ value, label }))} />
          <Button type="primary" onClick={() => setOpen(true)}>Создать пользователя</Button>
        </div>
      </div>
      <Table rowKey="id" dataSource={rows} scroll={{ x: true }} locale={{ emptyText: <Empty /> }} columns={[
        { title: "ID", dataIndex: "student_id" }, { title: "ФИО", dataIndex: "full_name" },
        { title: "Роль", dataIndex: "role", render: (v) => <Tag>{ROLE[v]}</Tag> },
        { title: "Группа", render: (_, u) => u.role === "student"
          ? <Select size="small" style={{ width: 150 }} allowClear placeholder="Не назначена" value={u.edu_group || undefined}
              options={(groups || []).map((g) => ({ value: g.name, label: g.name }))} onChange={(v) => patch(u, { edu_group: v || "" })} /> : "—" },
        { title: "Активен", render: (_, u) => <Switch checked={u.is_active} onChange={(v) => patch(u, { is_active: v })} /> },
        { title: "", render: (_, u) => <div className="flex gap-2"><Button size="small" onClick={() => { setEdit(u); editForm.setFieldsValue({ full_name: u.full_name, role: u.role }); }}>Изменить</Button><Button size="small" onClick={() => setPwUser(u)}>Сбросить пароль</Button></div> }]} />
      <Modal open={!!edit} title="Изменить пользователя" onCancel={() => setEdit(null)} onOk={() => editForm.submit()} okText="Сохранить" cancelText="Отмена">
        <Form form={editForm} layout="vertical" onFinish={saveEdit}>
          <Form.Item name="full_name" label="ФИО" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="role" label="Роль"><Select options={Object.entries(ROLE).map(([value, label]) => ({ value, label }))} /></Form.Item>
        </Form>
      </Modal>
      <Modal open={!!pwUser} title={`Сбросить пароль: ${pwUser?.full_name || ""}`} onCancel={() => setPwUser(null)} onOk={() => pwForm.submit()} okText="Сбросить" cancelText="Отмена">
        <Form form={pwForm} layout="vertical" onFinish={resetPw}>
          <Form.Item name="new_password" label="Новый временный пароль" rules={passwordRules} extra={PASSWORD_HINT}><Input.Password /></Form.Item>
          <p className="text-xs text-gray-500">Передайте пароль пользователю лично. Действие записывается в журнал.</p>
        </Form>
      </Modal>
      <Modal open={open} title="Новый пользователь" onCancel={() => setOpen(false)} onOk={() => form.submit()} okText="Создать" cancelText="Отмена">
        <Form form={form} layout="vertical" onFinish={create} initialValues={{ role: "student" }}>
          <Form.Item name="role" label="Роль"><Select options={Object.entries(ROLE).map(([value, label]) => ({ value, label }))} /></Form.Item>
          <Form.Item name="student_id" label="ID (12 цифр)" rules={[{ required: true, pattern: /^\d{12}$/, message: "12 цифр" }]}><Input maxLength={12} /></Form.Item>
          <Form.Item name="full_name" label="ФИО" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="password" label="Пароль" rules={passwordRules} extra={PASSWORD_HINT}><Input.Password /></Form.Item>
          {r === "student" && <Form.Item name="edu_group" label="Группа"><Select allowClear options={(groups || []).map((g) => ({ value: g.name, label: g.name }))} /></Form.Item>}
        </Form>
      </Modal>
    </div>
  );
}

/* Преподавание: предметы, группы и кто что ведёт */
function Teaching() {
  const { message } = AntApp.useApp();
  const [subjects, loadS] = useList("/admin/subjects/");
  const [groups, loadG] = useList("/admin/groups/");
  const [teachers] = useList("/admin/users/?role=teacher");
  const [asg, loadA] = useList("/admin/assignments/");
  const [form] = Form.useForm();
  const [subj, setSubj] = useState("");
  const [grp, setGrp] = useState("");
  const run = async (fn, ok, reload) => { try { await fn(); if (ok) message.success(ok); reload(); } catch (e) { message.error(e.message); } };

  if (!subjects || !groups || !teachers || !asg) return <Spin />;
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Преподавание</h1>
      <div className="grid gap-3 md:grid-cols-2">
        <Card title="Предметы" size="small">
          <div className="mb-2 flex gap-2"><Input value={subj} onChange={(e) => setSubj(e.target.value)} placeholder="Название предмета" />
            <Button type="primary" onClick={() => run(async () => { await api("/admin/subjects/", { method: "POST", body: { name: subj } }); setSubj(""); }, "Предмет добавлен", loadS)}>Добавить</Button></div>
          <div className="flex flex-wrap gap-2">{subjects.map((s) => <Popconfirm key={s.id} title="Удалить предмет и его назначения?" onConfirm={() => run(() => api(`/admin/subjects/${s.id}/`, { method: "DELETE" }), null, () => { loadS(); loadA(); })}><Tag closable onClose={(e) => e.preventDefault()}>{s.name}</Tag></Popconfirm>)}</div>
        </Card>
        <Card title="Группы" size="small">
          <div className="mb-2 flex gap-2"><Input value={grp} onChange={(e) => setGrp(e.target.value)} placeholder="Например: SWE25-201" />
            <Button type="primary" onClick={() => run(async () => { await api("/admin/groups/", { method: "POST", body: { name: grp } }); setGrp(""); }, "Группа добавлена", loadG)}>Добавить</Button></div>
          <div className="flex flex-wrap gap-2">{groups.map((g) => <Tag key={g.id}>{g.name} · {g.students} студ.</Tag>)}</div>
        </Card>
      </div>
      <Card title="Назначить преподавателю предмет и группу" size="small">
        <Form form={form} layout="inline" className="gap-y-2" onFinish={(v) => run(async () => { await api("/admin/assignments/", { method: "POST", body: { teacher: v.teacher, subjects: v.subjects, groups: v.groups } }); form.resetFields(); }, "Назначено", loadA)}>
          <Form.Item name="teacher" rules={[{ required: true, message: "Выберите" }]}><Select style={{ width: 220 }} placeholder="Преподаватель" options={teachers.map((t) => ({ value: t.id, label: t.full_name || t.student_id }))} /></Form.Item>
          <Form.Item name="subjects" rules={[{ required: true, message: "Выберите" }]}><Select mode="multiple" style={{ minWidth: 220 }} placeholder="Предметы (один или несколько)" options={opts(subjects)} /></Form.Item>
          <Form.Item name="groups" rules={[{ required: true, message: "Выберите" }]}><Select mode="multiple" style={{ minWidth: 200 }} placeholder="Группы (одна или несколько)" options={opts(groups.filter((g) => !g.is_archived))} /></Form.Item>
          <Button type="primary" htmlType="submit">Назначить</Button>
        </Form>
        <p className="mt-2 text-xs text-gray-500">Выбранные предметы и группы сочетаются все со всеми: например, 2 предмета × 3 группы = 6 назначений.</p>
        <Table className="mt-3" size="small" rowKey="id" dataSource={asg} pagination={{ pageSize: 8 }} scroll={{ x: true }} locale={{ emptyText: <Empty description="Назначений нет" /> }} columns={[
          { title: "Преподаватель", dataIndex: "teacher" }, { title: "Предмет", dataIndex: "subject" }, { title: "Группа", dataIndex: "group" },
          { title: "", render: (_, a) => <Popconfirm title="Снять назначение?" onConfirm={() => run(() => api(`/admin/assignments/${a.id}/`, { method: "DELETE" }), null, loadA)}><Button size="small" danger>Снять</Button></Popconfirm> }]} />
      </Card>
      <p className="text-sm text-gray-500">Студентов в группу назначают в разделе «Пользователи». Преподаватель увидит при создании экзамена только свои предметы и группы.</p>
    </div>
  );
}

/* Запросы преподавателей на удаление экзаменов с результатами */
function Requests() {
  const { message, modal } = AntApp.useApp();
  const [rows, load] = useList("/admin/deletion-requests/");
  const decide = (r, approve) => modal.confirm({
    title: approve ? `Удалить «${r.exam}» вместе со всеми результатами?` : "Отклонить запрос?",
    content: approve ? `Будут безвозвратно удалены экзамен, ${r.attempts} работ(ы) студентов, ответы и апелляции. Действие попадёт в журнал.` : "Экзамен останется без изменений.",
    okText: approve ? "Удалить всё" : "Отклонить", okButtonProps: { danger: approve }, cancelText: "Отмена",
    onOk: async () => { try { await api("/admin/deletion-requests/", { method: "POST", body: { id: r.id, approve } }); message.success(approve ? "Экзамен и результаты удалены" : "Запрос отклонён"); load(); } catch (e) { message.error(e.message); } },
  });
  if (!rows) return <Spin />;
  const ST = { pending: ["Ожидает", "orange"], approved: ["Одобрен", "green"], rejected: ["Отклонён", "red"] };
  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold">Запросы на удаление экзаменов</h1>
      <Table rowKey="id" dataSource={rows} scroll={{ x: true }} locale={{ emptyText: <Empty description="Запросов нет" /> }} columns={[
        { title: "Экзамен", dataIndex: "exam" }, { title: "Преподаватель", dataIndex: "teacher" },
        { title: "Работ студентов", dataIndex: "attempts", render: (v) => v ?? "—" }, { title: "Дата", dataIndex: "created_at", render: fmtDate },
        { title: "Статус", dataIndex: "status", render: (s) => <Tag color={ST[s][1]}>{ST[s][0]}</Tag> },
        { title: "", render: (_, r) => r.status === "pending" && <div className="flex gap-2"><Button size="small" danger onClick={() => decide(r, true)}>Разрешить</Button><Button size="small" onClick={() => decide(r, false)}>Отклонить</Button></div> }]} />
    </div>
  );
}

/* Апелляции: студент → администратор → преподаватель → администратор → студент */
function AppealsAdmin() {
  const { message } = AntApp.useApp();
  const [status, setStatus] = useState("todo");
  const [d, setD] = useState(null);
  const [cur, setCur] = useState(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => api("/admin/appeals/", { params: { status } }).then(setD).catch((e) => { message.error(e.message); setD({ results: [] }); }), [status, message]);
  useEffect(() => { load(); }, [load]);
  const act = async (action) => {
    setBusy(true);
    try { await api("/admin/appeals/", { method: "POST", body: { id: cur.id, action, note } }); message.success("Готово"); setCur(null); setNote(""); load(); }
    catch (e) { message.error(e.message); } finally { setBusy(false); }
  };
  if (!d) return <Spin />;
  const first = cur?.status === "submitted", second = cur?.status === "teacher_done";
  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold">Апелляции</h1>
      <Select value={status} style={{ width: 280 }} onChange={setStatus} options={[{ value: "todo", label: "Требуют моего действия" },
        ...Object.entries(APPEAL_STATUS).map(([value, [label]]) => ({ value, label })), { value: "", label: "Все" }]} />
      <Table rowKey="id" dataSource={d.results} scroll={{ x: true }} locale={{ emptyText: <Empty description="Апелляций нет" /> }} columns={[
        { title: "Студент", dataIndex: "student" }, { title: "Группа", dataIndex: "group" }, { title: "Экзамен", dataIndex: "exam" },
        { title: "Преподаватель", dataIndex: "teacher" }, { title: "Подана", dataIndex: "created_at", render: fmtDate },
        { title: "Статус", dataIndex: "status", render: (s) => <Tag color={APPEAL_STATUS[s][1]}>{APPEAL_STATUS[s][0]}</Tag> },
        { title: "", render: (_, r) => <Button size="small" type={["submitted", "teacher_done"].includes(r.status) ? "primary" : "default"} onClick={() => { setCur(r); setNote(""); }}>Открыть</Button> }]} />
      <Modal open={!!cur} width={700} title="Апелляция" onCancel={() => setCur(null)} footer={
        first ? [<Button key="r" danger loading={busy} onClick={() => act("reject")}>Отклонить</Button>, <Button key="f" type="primary" loading={busy} onClick={() => act("forward")}>Передать преподавателю</Button>]
        : second ? [<Button key="b" loading={busy} onClick={() => act("return")}>Вернуть преподавателю</Button>, <Button key="a" type="primary" loading={busy} onClick={() => act("approve")}>Подтвердить и отправить студенту</Button>]
        : null}>
        {cur && <div className="space-y-3">
          <AppealCard a={cur} />
          {(first || second) && <Input.TextArea rows={3} value={note} onChange={(e) => setNote(e.target.value)}
            placeholder={first ? "Комментарий (для отклонения — причина, обязательна; студент её увидит)" : "Комментарий (для возврата — обязателен)"} />}
          {second && cur.teacher_accept && cur.teacher_new_score != null && <p className="text-sm text-amber-700">При подтверждении итоговый балл студента изменится с {cur.score} на {cur.teacher_new_score}.</p>}
        </div>}
      </Modal>
    </div>
  );
}

function Audit() {
  const { message } = AntApp.useApp();
  const [f, setF] = useState({});
  const [page, setPage] = useState(1);
  const [d, setD] = useState({ results: [], count: 0 });
  const [loading, setLoading] = useState(true);
  const size = 50;
  useEffect(() => {
    setLoading(true);
    api("/admin/audit/", { params: { ...f, limit: size, offset: (page - 1) * size } }).then(setD).catch((e) => message.error(e.message)).finally(() => setLoading(false));
  }, [f, page, message]);
  const set = (k) => (v) => { setPage(1); setF((x) => ({ ...x, [k]: v || undefined })); };
  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold">Журнал действий</h1>
      <div className="flex flex-wrap gap-2">
        <Input allowClear style={{ width: 200 }} placeholder="Пользователь (имя или ID)" onChange={(e) => set("user")(e.target.value)} />
        <Select allowClear style={{ width: 170 }} placeholder="Роль" onChange={set("role")} options={Object.entries(ROLE).map(([value, label]) => ({ value, label }))} />
        <Input allowClear style={{ width: 200 }} placeholder="Действие (например appeal_decided)" onChange={(e) => set("action")(e.target.value)} />
        <Input type="date" style={{ width: 150 }} onChange={(e) => set("date_from")(e.target.value)} />
        <Input type="date" style={{ width: 150 }} onChange={(e) => set("date_to")(e.target.value)} />
      </div>
      <Table rowKey="id" size="small" loading={loading} dataSource={d.results} scroll={{ x: true }}
        pagination={{ current: page, pageSize: size, total: d.count, showSizeChanger: false, onChange: setPage }} columns={[
        { title: "Время", dataIndex: "created_at", render: fmtDate }, { title: "Пользователь", dataIndex: "user" },
        { title: "Роль", dataIndex: "role", render: (v) => ROLE[v] || "—" },
        { title: "Действие", dataIndex: "action" }, { title: "Ресурс", dataIndex: "resource" },
        { title: "Было", dataIndex: "previous", ellipsis: true }, { title: "Стало", dataIndex: "new", ellipsis: true }, { title: "IP", dataIndex: "ip" }]} />
    </div>
  );
}

export default function Admin() {
  return (
    <AntApp>
      <Routes>
        <Route index element={<Navigate to="users" replace />} />
        <Route path="dashboard" element={<Navigate to="/admin/users" replace />} />
        <Route path="users" element={<Users />} />
        <Route path="teaching" element={<Teaching />} />
        <Route path="requests" element={<Requests />} />
        <Route path="appeals" element={<AppealsAdmin />} />
        <Route path="audit" element={<Audit />} />
        <Route path="profile" element={<Profile />} />
        <Route path="*" element={<Navigate to="/admin/users" replace />} />
      </Routes>
    </AntApp>
  );
}
