import { useCallback, useEffect, useState } from "react";
import { App, Button, Empty, Input, InputNumber, Modal, Spin, Table, Tag } from "antd";
import { api } from "../../api/client.js";
import { fmtDate } from "../../components/common/constants.js";

// Ручная проверка письменных ответов (FR-11, FR-13)
export default function Grading() {
  const { message, modal } = App.useApp();
  const [rows, setRows] = useState(null);
  const [cur, setCur] = useState(null);
  const [g, setG] = useState({});
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api("/teacher/grading/").then(setRows).catch((e) => { message.error(e.message); setRows([]); }), [message]);
  useEffect(() => { load(); }, [load]);

  const open = (r) => { setCur(r); setG(Object.fromEntries(r.answers.map((a) => [a.id, { points: null, feedback: "" }]))); };
  const upd = (id, patch) => setG((x) => ({ ...x, [id]: { ...x[id], ...patch } }));
  const total = cur ? Object.values(g).reduce((s, x) => s + (x.points || 0), 0) : 0;

  const submit = () => {
    if (Object.values(g).some((x) => x.points === null || x.points === undefined)) {
      return message.warning("Выставьте баллы за каждый письменный ответ (0 тоже нужно ввести)");
    }
    modal.confirm({
    title: "Подтвердить итоговую оценку?",
    content: `Итого ${total} баллов. После подтверждения оценка будет зафиксирована, прямое изменение невозможно.`,
    okText: "Зафиксировать", cancelText: "Назад",
    onOk: async () => {
      setBusy(true);
      try {
        await api("/teacher/grading/", { method: "POST", body: { attempt: cur.id, grades: Object.entries(g).map(([id, v]) => ({ id: Number(id), ...v })) } });
        message.success("Оценка выставлена");
        setCur(null); load();
      } catch (e) { message.error(e.message); } finally { setBusy(false); }
    },
  });
  };

  if (!rows) return <Spin />;
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2"><h1 className="text-xl font-semibold">Письменные работы</h1><Tag color="orange">Ожидают: {rows.length}</Tag></div>
      <Table rowKey="id" dataSource={rows} scroll={{ x: true }} locale={{ emptyText: <Empty description="Нет работ на проверку" /> }} columns={[
        { title: "Студент", dataIndex: "student" }, { title: "Группа", dataIndex: "group" }, { title: "Экзамен", dataIndex: "exam" },
        { title: "Сдано", dataIndex: "submitted_at", render: fmtDate },
        { title: "", render: (_, r) => <Button type="primary" size="small" onClick={() => open(r)}>Проверить</Button> }]} />
      <Modal open={!!cur} width={760} title={cur && `${cur.student} — ${cur.exam}`} onCancel={() => setCur(null)} okText="Завершить проверку" cancelText="Закрыть" onOk={submit} confirmLoading={busy}>
        {cur?.answers.map((a, k) => (
          <div key={a.id} className="mb-4 rounded-xl border border-gray-200 p-3">
            <p className="font-medium">{k + 1}. {a.question}</p>
            <p className="my-2 whitespace-pre-wrap rounded bg-gray-50 p-2">{a.answer || <i className="text-gray-400">Ответ не дан</i>}</p>
            <div className="flex items-center gap-2">Баллы: <InputNumber min={0} max={a.max} value={g[a.id]?.points} onChange={(v) => upd(a.id, { points: v })} /> из {a.max}</div>
            <Input.TextArea className="mt-2" rows={2} placeholder="Комментарий для студента" value={g[a.id]?.feedback} onChange={(e) => upd(a.id, { feedback: e.target.value })} />
          </div>
        ))}
        <p className="text-right font-semibold">Итого: {total}</p>
      </Modal>
    </div>
  );
}
