import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { App, Button, Card, Dropdown, Input, Popconfirm, Segmented, Select, Space, Switch, Table, Tag } from "antd";
import {
  PlusOutlined,
  MoreOutlined,
  EditOutlined,
  QuestionCircleOutlined,
  CopyOutlined,
  InboxOutlined,
  DeleteOutlined,
} from "@ant-design/icons";

import { api } from "../../../api/client.js";
import { EXAM_TYPE, STATUS, fmtDate } from "../../../components/common/constants.js";

const STATUS_FILTER = [
  { label: "Все", value: "" },
  { label: "Черновики", value: "draft" },
  { label: "Опубликованные", value: "published" },
  { label: "Скрытые", value: "hidden" },
  { label: "Архив", value: "archived" },
];

export default function MyExams() {
  const navigate = useNavigate();
  const { message, modal } = App.useApp();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("");
  const [examType, setExamType] = useState("");
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await api("/exams/", { params: { status, exam_type: examType, search } }));
    } catch (e) {
      message.error(e.message);
    } finally {
      setLoading(false);
    }
  }, [status, examType, search, message]);

  useEffect(() => {
    load();
  }, [load]);

  // Общий обработчик действий над экзаменом
  const act = async (id, action, okText) => {
    try {
      await api(`/exams/${id}/${action}/`, { method: "POST" });
      message.success(okText);
      load();
    } catch (e) {
      // Если публикация не прошла — показываем все причины списком
      if (e.data?.problems) {
        modal.warning({
          title: "Экзамен нельзя опубликовать",
          content: (
            <ul className="pl-4 m-0">
              {e.data.problems.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          ),
        });
      } else {
        message.error(e.message);
      }
    }
  };

  const remove = async (id) => {
    try {
      await api(`/exams/${id}/`, { method: "DELETE" });
      message.success("Экзамен удалён");
      load();
    } catch (e) {
      message.error(e.message);
    }
  };

  const columns = [
    {
      title: "Экзамен",
      dataIndex: "title",
      render: (t, r) => (
        <div>
          <div className="font-semibold text-slate-900">{t}</div>
          <div className="text-slate-500 text-sm">{r.subject}</div>
        </div>
      ),
    },
    {
      title: "Тип",
      dataIndex: "exam_type",
      responsive: ["md"],
      render: (v) => <Tag color={EXAM_TYPE[v].color}>{EXAM_TYPE[v].label}</Tag>,
    },
    {
      title: "Группы",
      dataIndex: "group_names",
      responsive: ["lg"],
      render: (g) => (g.length ? g.map((n) => <Tag key={n}>{n}</Tag>) : <span className="text-slate-400">—</span>),
    },
    { title: "Начало", dataIndex: "start_at", responsive: ["lg"], render: fmtDate },
    { title: "Вопросов", dataIndex: "questions_count", responsive: ["md"], align: "center" },
    {
      title: "Статус",
      dataIndex: "status",
      render: (v) => <Tag color={STATUS[v].color}>{STATUS[v].label}</Tag>,
    },
    {
      title: "Виден студентам",
      key: "visible",
      align: "center",
      render: (_, r) => (
        <Popconfirm
          title={r.status === "published" ? "Скрыть экзамен от студентов?" : "Опубликовать экзамен?"}
          okText="Да"
          cancelText="Отмена"
          disabled={r.status === "archived"}
          onConfirm={() =>
            r.status === "published"
              ? act(r.id, "hide", "Экзамен скрыт")
              : act(r.id, "publish", "Экзамен опубликован")
          }
        >
          <Switch checked={r.status === "published"} disabled={r.status === "archived"} />
        </Popconfirm>
      ),
    },
    {
      title: "",
      key: "actions",
      width: 60,
      render: (_, r) => (
        <Dropdown
          trigger={["click"]}
          menu={{
            items: [
              { key: "edit", icon: <EditOutlined />, label: "Редактировать", disabled: r.status === "archived" },
              { key: "questions", icon: <QuestionCircleOutlined />, label: "Вопросы" },
              { key: "duplicate", icon: <CopyOutlined />, label: "Дублировать" },
              { key: "archive", icon: <InboxOutlined />, label: "В архив", disabled: r.status === "archived" },
              { type: "divider" },
              { key: "delete", icon: <DeleteOutlined />, label: "Удалить", danger: true },
            ],
            onClick: ({ key }) => {
              if (key === "edit") navigate(`/teacher/exams/${r.id}/edit`);
              if (key === "questions") navigate(`/teacher/exams/${r.id}/questions`);
              if (key === "duplicate") act(r.id, "duplicate", "Копия создана как черновик");
              if (key === "archive")
                modal.confirm({
                  title: "Отправить экзамен в архив?",
                  content: "Архивный экзамен нельзя редактировать и публиковать.",
                  okText: "В архив",
                  cancelText: "Отмена",
                  onOk: () => act(r.id, "archive", "Экзамен в архиве"),
                });
              if (key === "delete")
                modal.confirm({
                  title: `Удалить «${r.title}»?`,
                  content: "Экзамен и все его вопросы будут удалены без возможности восстановления.",
                  okText: "Удалить",
                  okButtonProps: { danger: true },
                  cancelText: "Отмена",
                  onOk: () => remove(r.id),
                });
            },
          }}
        >
          <Button type="text" icon={<MoreOutlined />} aria-label="Действия" />
        </Dropdown>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-slate-900 m-0">Мои экзамены</h1>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/teacher/exams/new")}>
          Создать экзамен
        </Button>
      </div>

      <Card variant="borderless">
        <Space wrap className="mb-4">
          <Segmented options={STATUS_FILTER} value={status} onChange={setStatus} />
          <Select
            value={examType}
            onChange={setExamType}
            style={{ width: 160 }}
            options={[
              { value: "", label: "Все типы" },
              { value: "test", label: "Тест" },
              { value: "written", label: "Письменный" },
            ]}
          />
          <Input.Search
            allowClear
            placeholder="Поиск по названию или предмету"
            onSearch={setSearch}
            style={{ width: 280 }}
          />
        </Space>

        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={rows}
          pagination={{ pageSize: 10, hideOnSinglePage: true }}
          locale={{ emptyText: "Экзаменов пока нет. Нажмите «Создать экзамен»." }}
          scroll={{ x: true }}
        />
      </Card>
    </div>
  );
}
