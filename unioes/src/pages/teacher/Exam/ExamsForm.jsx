import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import {
  App, Alert, Button, Card, Col, DatePicker, Form, Input, InputNumber,
  Radio, Row, Select, Skeleton, Switch,
} from "antd";
import dayjs from "dayjs";

import { api } from "../../../api/client.js";

const { RangePicker } = DatePicker;

export default function ExamForm() {
  const { id } = useParams();
  const isEdit = Boolean(id);
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [form] = Form.useForm();

  const [groups, setGroups] = useState([]);
  const [exam, setExam] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        setGroups(await api("/groups/"));
        if (isEdit) {
          const e = await api(`/exams/${id}/`);
          setExam(e);
          form.setFieldsValue({ ...e, range: [dayjs(e.start_at), dayjs(e.end_at)] });
        }
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, [id, isEdit, form]);

  const onFinish = async ({ range, ...values }) => {
    setSaving(true);
    try {
      const body = {
        ...values,
        start_at: range[0].toISOString(),
        end_at: range[1].toISOString(),
      };
      const saved = await api(isEdit ? `/exams/${id}/` : "/exams/", {
        method: isEdit ? "PATCH" : "POST",
        body,
      });
      message.success(isEdit ? "Изменения сохранены" : "Экзамен создан. Теперь добавьте вопросы");
      navigate(`/teacher/exams/${saved.id}/questions`);
    } catch (e) {
      message.error(e.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <Skeleton active paragraph={{ rows: 8 }} />;
  if (error) return <Alert type="error" showIcon title={error} />;

  const hasQuestions = (exam?.questions_count || 0) > 0;

  return (
    <div className="space-y-4 max-w-4xl">
      <h1 className="text-2xl font-bold text-slate-900 m-0">
        {isEdit ? "Редактирование экзамена" : "Создание экзамена"}
      </h1>

      <Form
        form={form}
        layout="vertical"
        onFinish={onFinish}
        requiredMark="optional"
        initialValues={{
          exam_type: "test",
          duration_minutes: 60,
          max_score: 100,
          passing_score: 55,
          randomize_questions: false,
          allow_multiple_attempts: false,
          allow_appeals: true,
          show_results_immediately: true,
        }}
      >
        <Card variant="borderless" title="Основная информация" className="mb-4">
          <Form.Item label="Название" name="title" rules={[{ required: true, message: "Введите название" }]}>
            <Input placeholder="Например: Алгоритмы и структуры данных — итоговый" />
          </Form.Item>
          <Row gutter={16}>
            <Col xs={24} md={12}>
              <Form.Item label="Предмет" name="subject" rules={[{ required: true, message: "Введите предмет" }]}>
                <Input />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item
                label="Тип экзамена"
                name="exam_type"
                extra={hasQuestions ? "Тип нельзя менять, пока в экзамене есть вопросы" : undefined}
              >
                <Radio.Group disabled={hasQuestions} optionType="button" buttonStyle="solid">
                  <Radio.Button value="test">Тест</Radio.Button>
                  <Radio.Button value="written">Письменный</Radio.Button>
                </Radio.Group>
              </Form.Item>
            </Col>
          </Row>
          <Form.Item label="Описание" name="description">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item
            label="Группы"
            name="groups"
            rules={[{ required: true, type: "array", min: 1, message: "Выберите хотя бы одну группу" }]}
          >
            <Select
              mode="multiple"
              placeholder="Выберите одну или несколько групп"
              options={groups.map((g) => ({ value: g.id, label: g.name }))}
            />
          </Form.Item>
        </Card>

        <Card variant="borderless" title="Настройки экзамена" className="mb-4">
          <Row gutter={16}>
            <Col xs={24} md={12}>
              <Form.Item label="Период проведения" name="range" rules={[{ required: true, message: "Укажите период" }]}>
                <RangePicker showTime={{ format: "HH:mm" }} format="DD.MM.YYYY HH:mm" style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="Длительность (мин)" name="duration_minutes" rules={[{ required: true }]}>
                <InputNumber min={1} max={600} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="Максимальный балл" name="max_score" rules={[{ required: true }]}>
                <InputNumber min={1} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item
                label="Проходной балл"
                name="passing_score"
                dependencies={["max_score"]}
                rules={[
                  { required: true },
                  ({ getFieldValue }) => ({
                    validator: (_, v) =>
                      v == null || v <= getFieldValue("max_score")
                        ? Promise.resolve()
                        : Promise.reject(new Error("Не больше максимального балла")),
                  }),
                ]}
              >
                <InputNumber min={0} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
          </Row>

          <div className="grid gap-3 sm:grid-cols-2">
            {[
              ["randomize_questions", "Перемешивать вопросы"],
              ["allow_multiple_attempts", "Разрешить несколько попыток"],
              ["allow_appeals", "Разрешить апелляции по вопросам"],
              ["show_results_immediately", "Показывать результат сразу"],
            ].map(([name, label]) => (
              <div key={name} className="flex items-center justify-between rounded-lg bg-slate-50 px-4 py-3">
                <span>{label}</span>
                <Form.Item name={name} valuePropName="checked" noStyle>
                  <Switch />
                </Form.Item>
              </div>
            ))}
          </div>
        </Card>

        <div className="flex gap-3">
          <Button type="primary" htmlType="submit" loading={saving} size="large">
            {isEdit ? "Сохранить" : "Создать и добавить вопросы"}
          </Button>
          <Button size="large" onClick={() => navigate("/teacher/exams")}>
            Отмена
          </Button>
        </div>
      </Form>
    </div>
  );
}
    