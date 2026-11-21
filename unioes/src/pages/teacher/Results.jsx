import { useCallback, useEffect, useState } from "react";
import { App, Button, Empty, Select, Table, Tag } from "antd";
import { api } from "../../api/client.js";
import { fmtDate } from "../../components/common/constants.js";

// Результаты студентов по экзаменам преподавателя
export default function Results() {
  const { message, modal } = App.useApp();
  const [data, setData] = useState({ results: [], exams: [], count: 0 });
  const [exam, setExam] = useState();
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const size = 20;

  const load = useCallback(async () => {
    setLoading(true);
    try { setData(await api("/teacher/results/", { params: { exam, limit: size, offset: (page - 1) * size } })); }
    catch (e) { message.error(e.message); } finally { setLoading(false); }
  }, [exam, page, message]);
  useEffect(() => { load(); }, [load]);

  const sel = data.exams.find((e) => e.id === exam);
  const publish = () => modal.confirm({
    title: "Опубликовать результаты?", content: "Студенты увидят свои баллы и оценки.", okText: "Опубликовать", cancelText: "Отмена",
    onOk: async () => { try { await api("/teacher/results/", { method: "POST", body: { exam } }); message.success("Результаты опубликованы"); load(); } catch (e) { message.error(e.message); } },
  });
  const avg = data.results.filter((r) => r.percent !== null);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold">Результаты студентов</h1>
        <div className="flex gap-2">
          <Select allowClear placeholder="Все экзамены" style={{ width: 260 }} value={exam} onChange={(v) => { setExam(v); setPage(1); }}
            options={data.exams.map((e) => ({ value: e.id, label: e.title }))} />
          {sel && !sel.show_immediately && !sel.results_published && <Button type="primary" onClick={publish}>Опубликовать результаты</Button>}
        </div>
      </div>
      {sel && <p className="text-sm text-gray-500">{sel.results_published || sel.show_immediately ? "Студенты видят свои результаты." : "Результаты скрыты от студентов до публикации."}
        {avg.length > 0 && ` Средний результат на странице: ${Math.round(avg.reduce((s, r) => s + r.percent, 0) / avg.length)}%`}</p>}
      <Table rowKey="id" loading={loading} dataSource={data.results} scroll={{ x: true }} locale={{ emptyText: <Empty description="Сданных работ пока нет" /> }}
        pagination={{ current: page, pageSize: size, total: data.count, showSizeChanger: false, onChange: setPage }} columns={[
          { title: "Студент", dataIndex: "student" }, { title: "ID", dataIndex: "student_id" }, { title: "Группа", dataIndex: "group" },
          { title: "Экзамен", dataIndex: "exam" }, { title: "Сдано", dataIndex: "submitted_at", render: fmtDate },
          { title: "Балл", render: (_, r) => (r.score === null ? "—" : `${r.score} / ${r.max_score}`) },
          { title: "%", dataIndex: "percent", render: (v) => v ?? "—" },
          { title: "Выходы", dataIndex: "violations", render: (v) => (v ? <Tag color={v >= 3 ? "red" : "orange"}>{v}</Tag> : 0) },
          { title: "Итог", render: (_, r) => r.status === "waiting" ? <Tag color="orange">Ждёт проверки</Tag> : <Tag color={r.passed ? "green" : "red"}>{r.passed ? "Сдал" : "Не сдал"}</Tag> },
          { title: "", dataIndex: "revised", render: (v) => v && <Tag color="purple">Пересмотрен</Tag> }]} />
    </div>
  );
}
