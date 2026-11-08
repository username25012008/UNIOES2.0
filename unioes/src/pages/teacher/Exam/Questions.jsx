import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import {
  App, Alert, Button, Card, Empty, Form, Input, InputNumber, Modal,
  Popconfirm, Progress, Select, Skeleton, Space, Tag,
} from "antd";
import { ArrowLeftOutlined, DeleteOutlined, EditOutlined, MinusCircleOutlined, PlusOutlined } from "@ant-design/icons";

import { api } from "../../../api/client.js";
import { DIFFICULTY, EXAM_TYPE, QUESTION_TYPE, STATUS } from "../../../components/common/constants.js";

const DIFF_OPTIONS = Object.entries(DIFFICULTY).map(([value, d]) => ({ value, label: d.label }));

export default function Questions() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { message, modal } = App.useApp();
  const [form] = Form.useForm();

  const [exam, setExam] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(null); // null | "new" | question
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [e, q] = await Promise.all([api(`/exams/${id}/`), api(`/exams/${id}/questions/`)]);
      setExam(e);
      setQuestions(q);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const qtype = Form.useWatch("question_type", form);
  const options = Form.useWatch("options", form) || [];

  if (loading) return <Skeleton active paragraph={{ rows: 8 }} />;
  if (error) return <Alert type="error" showIcon title={error} />;

  const isWritten = exam.exam_type === "written";
  const locked = exam.status === "published" || exam.status === "archived";
  const totalPoints = questions.reduce((s, q) => s + q.points, 0);
  const dist = exam.difficulty_distribution;

  const openForm = (q) => {
    setEditing(q || "new");
    form.resetFields();
    form.setFieldsValue(
      q
        ? {
            ...q,
            // Для одиночного выбора Select ждёт число, а не список
            correct_answers: q.question_type === "single" ? q.correct_answers[0] : q.correct_answers,
          }
        : {
            question_type: isWritten ? "written" : "single",
            options: ["", ""],
            correct_answers: undefined,
            points: 1,
            difficulty: "medium",
          }
    );
  };

  const save = async (values) => {
    setSaving(true);
    try {
      // Для вопроса с одним ответом форма отдаёт число, API ждёт список
      const correct = Array.isArray(values.correct_answers)
        ? values.correct_answers
        : values.correct_answers == null
        ? []
        : [values.correct_answers];
      const body = { ...values, correct_answers: correct };
      if (editing === "new") {
        await api(`/exams/${id}/questions/`, { method: "POST", body });
      } else {
        await api(`/exams/${id}/questions/${editing.id}/`, { method: "PATCH", body });
      }
      message.success("Вопрос сохранён");
      setEditing(null);
      load();
    } catch (e) {
      message.error(e.message);
    } finally {
      setSaving(false);
    }
  };

  const remove = async (qid) => {
    try {
      await api(`/exams/${id}/questions/${qid}/`, { method: "DELETE" });
      message.success("Вопрос удалён");
      load();
    } catch (e) {
      message.error(e.message);
    }
  };

  const publish = async () => {
    try {
      await api(`/exams/${id}/publish/`, { method: "POST" });
      message.success("Экзамен опубликован");
      load();
    } catch (e) {
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
      } else message.error(e.message);
    }
  };

  const hide = async () => {
    try {
      await api(`/exams/${id}/hide/`, { method: "POST" });
      message.success("Экзамен скрыт — теперь вопросы можно редактировать");
      load();
    } catch (e) {
      message.error(e.message);
    }
  };

  return (
    <div className="space-y-4">
      <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate("/teacher/exams")}>
        К списку экзаменов
      </Button>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 m-0">{exam.title}</h1>
          <Space className="mt-2" wrap>
            <Tag color={EXAM_TYPE[exam.exam_type].color}>{EXAM_TYPE[exam.exam_type].label}</Tag>
            <Tag color={STATUS[exam.status].color}>{STATUS[exam.status].label}</Tag>
            <span className="text-slate-500">{exam.subject}</span>
          </Space>
        </div>
        <Space wrap>
          <Button onClick={() => navigate(`/teacher/exams/${id}/edit`)} disabled={exam.status === "archived"}>
            Настройки
          </Button>
          {exam.status === "published" ? (
            <Button onClick={hide}>Скрыть от студентов</Button>
          ) : (
            <Button type="primary" onClick={publish} disabled={exam.status === "archived"}>
              Опубликовать
            </Button>
          )}
        </Space>
      </div>

      {locked && (
        <Alert
          type="info"
          showIcon
          title={
            exam.status === "published"
              ? "Экзамен опубликован: вопросы менять нельзя. Скройте экзамен, чтобы редактировать."
              : "Экзамен в архиве: редактирование недоступно."
          }
        />
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card variant="borderless" title="Баллы">
          <Progress
            percent={Math.min(100, Math.round((totalPoints / exam.max_score) * 100))}
            status={totalPoints === exam.max_score ? "success" : totalPoints > exam.max_score ? "exception" : "active"}
          />
          <div className="text-slate-600">
            Сумма баллов вопросов: <b>{totalPoints}</b> из {exam.max_score}
          </div>
          {totalPoints !== exam.max_score && questions.length > 0 && (
            <div className="text-amber-600 text-sm mt-1">Для публикации сумма должна равняться максимальному баллу</div>
          )}
        </Card>

        {!isWritten && (
          <Card variant="borderless" title="Распределение по сложности" className="lg:col-span-2">
            {questions.length === 0 ? (
              <span className="text-slate-400">Появится после добавления вопросов</span>
            ) : (
              Object.entries(DIFFICULTY).map(([k, d]) => (
                <div key={k} className="flex items-center gap-3">
                  <span className="w-20">{d.label}</span>
                  <Progress
                    percent={Math.round(((dist[k] || 0) / questions.length) * 100)}
                    strokeColor={d.color}
                    format={() => dist[k] || 0}
                  />
                </div>
              ))
            )}
          </Card>
        )}
        {isWritten && (
          <Card variant="borderless" title="Распределение по сложности" className="lg:col-span-2">
            {Object.entries(DIFFICULTY).map(([k, d]) => (
              <Tag key={k} color={d.color}>
                {d.label}: {dist[k] || 0}
              </Tag>
            ))}
          </Card>
        )}
      </div>

      <Card
        variant="borderless"
        title={`Вопросы (${questions.length})`}
        extra={
          <Button type="primary" icon={<PlusOutlined />} disabled={locked} onClick={() => openForm()}>
            Добавить вопрос
          </Button>
        }
      >
        {questions.length === 0 ? (
          <Empty description="Вопросов пока нет" />
        ) : (
          <div className="space-y-3">
            {questions.map((q, i) => (
              <div key={q.id} className="rounded-xl border border-slate-200 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-semibold text-slate-900">
                      {i + 1}. {q.text}
                    </div>
                    <Space className="mt-2" wrap size={[4, 4]}>
                      <Tag>{QUESTION_TYPE[q.question_type]}</Tag>
                      <Tag color={DIFFICULTY[q.difficulty].color}>{DIFFICULTY[q.difficulty].label}</Tag>
                      <Tag color="blue">{q.points} б.</Tag>
                    </Space>
                  </div>
                  <Space>
                    <Button icon={<EditOutlined />} disabled={locked} onClick={() => openForm(q)} aria-label="Редактировать" />
                    <Popconfirm
                      title="Удалить вопрос?"
                      okText="Удалить"
                      cancelText="Отмена"
                      okButtonProps={{ danger: true }}
                      disabled={locked}
                      onConfirm={() => remove(q.id)}
                    >
                      <Button danger icon={<DeleteOutlined />} disabled={locked} aria-label="Удалить" />
                    </Popconfirm>
                  </Space>
                </div>
                {q.options.length > 0 && (
                  <ul className="mt-3 mb-0 pl-5 text-slate-700">
                    {q.options.map((o, oi) => (
                      <li key={oi} className={q.correct_answers.includes(oi) ? "text-green-700 font-medium" : ""}>
                        {o}
                        {q.correct_answers.includes(oi) && " ✓"}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      <Modal
        open={Boolean(editing)}
        title={editing === "new" ? "Новый вопрос" : "Редактирование вопроса"}
        onCancel={() => setEditing(null)}
        onOk={() => form.submit()}
        okText="Сохранить"
        cancelText="Отмена"
        confirmLoading={saving}
        width={640}
        destroyOnHidden
        forceRender
      >
        <Form form={form} layout="vertical" onFinish={save}>
          <Form.Item label="Текст вопроса" name="text" rules={[{ required: true, message: "Введите текст вопроса" }]}>
            <Input.TextArea rows={3} />
          </Form.Item>

          <div className="grid gap-4 sm:grid-cols-3">
            <Form.Item label="Тип" name="question_type">
              <Select
                disabled={isWritten}
                options={
                  isWritten
                    ? [{ value: "written", label: QUESTION_TYPE.written }]
                    : [
                        { value: "single", label: QUESTION_TYPE.single },
                        { value: "multiple", label: QUESTION_TYPE.multiple },
                      ]
                }
                onChange={() => form.setFieldValue("correct_answers", undefined)}
              />
            </Form.Item>
            <Form.Item label="Сложность" name="difficulty">
              <Select options={DIFF_OPTIONS} />
            </Form.Item>
            <Form.Item label="Баллы" name="points" rules={[{ required: true }]}>
              <InputNumber min={1} style={{ width: "100%" }} />
            </Form.Item>
          </div>

          {qtype !== "written" && (
            <>
              <Form.List name="options">
                {(fields, { add, remove: rm }) => (
                  <>
                    <div className="mb-2">Варианты ответа</div>
                    {fields.map((f, idx) => (
                      <div key={f.key} className="flex items-start gap-2">
                        <Form.Item
                          name={f.name}
                          className="flex-1"
                          rules={[{ required: true, whitespace: true, message: "Введите вариант" }]}
                        >
                          <Input placeholder={`Вариант ${idx + 1}`} />
                        </Form.Item>
                        {fields.length > 2 && (
                          <Button
                            type="text"
                            danger
                            icon={<MinusCircleOutlined />}
                            onClick={() => {
                              rm(f.name);
                              form.setFieldValue("correct_answers", undefined);
                            }}
                            aria-label="Убрать вариант"
                          />
                        )}
                      </div>
                    ))}
                    {fields.length < 8 && (
                      <Button type="dashed" icon={<PlusOutlined />} onClick={() => add("")} className="mb-4">
                        Добавить вариант
                      </Button>
                    )}
                  </>
                )}
              </Form.List>

              <Form.Item
                label={qtype === "multiple" ? "Правильные ответы" : "Правильный ответ"}
                name="correct_answers"
                rules={[{ required: true, message: "Укажите правильный ответ" }]}
              >
                <Select
                  mode={qtype === "multiple" ? "multiple" : undefined}
                  placeholder="Выберите из вариантов выше"
                  options={options.map((o, i) => ({ value: i, label: o || `Вариант ${i + 1}` }))}
                />
              </Form.Item>
            </>
          )}
        </Form>
      </Modal>
    </div>
  );
}
