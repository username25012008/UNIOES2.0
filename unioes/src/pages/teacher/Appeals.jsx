import { useCallback, useEffect, useState } from "react";
import { App, Alert, Button, Empty, Input, InputNumber, Modal, Spin, Table, Tag } from "antd";
import { api } from "../../api/client.js";
import { fmtDate } from "../../components/common/constants.js";
import AppealCard from "../../components/common/AppealCard.jsx";
import { APPEAL_STATUS } from "../../components/common/constants.js";

// Апелляции, которые администратор переслал преподавателю. Решение преподавателя — рекомендация:
// оценка меняется только после подтверждения администратором.
export default function Appeals() {
  const { message } = App.useApp();
  const [rows, setRows] = useState(null);
  const [cur, setCur] = useState(null);
  const [text, setText] = useState("");
  const [score, setScore] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api("/teacher/appeals/").then(setRows).catch((e) => { message.error(e.message); setRows([]); }), [message]);
  useEffect(() => { load(); }, [load]);

  const open = (r) => { setCur(r); setText(""); setScore(null); };
  const decide = async (accept) => {
    if (!text.trim()) return message.warning("Напишите обоснование");
    setBusy(true);
    try {
      await api("/teacher/appeals/", { method: "POST", body: { id: cur.id, accept, decision: text, new_score: accept ? score : null } });
      message.success("Решение отправлено администратору");
      setCur(null); load();
    } catch (e) { message.error(e.message); } finally { setBusy(false); }
  };

  if (!rows) return <Spin />;
  const mine = cur?.status === "review";
  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold">Апелляции студентов</h1>
      <Table rowKey="id" dataSource={rows} scroll={{ x: true }} locale={{ emptyText: <Empty description="Апелляций нет" /> }} columns={[
        { title: "Студент", dataIndex: "student" }, { title: "Группа", dataIndex: "group" }, { title: "Экзамен", dataIndex: "exam" },
        { title: "Подана", dataIndex: "created_at", render: fmtDate },
        { title: "Статус", dataIndex: "status", render: (s) => <Tag color={APPEAL_STATUS[s][1]}>{APPEAL_STATUS[s][0]}</Tag> },
        { title: "", render: (_, r) => <Button size="small" type={r.status === "review" ? "primary" : "default"} onClick={() => open(r)}>{r.status === "review" ? "Рассмотреть" : "Открыть"}</Button> }]} />
      <Modal open={!!cur} title="Рассмотрение апелляции" onCancel={() => setCur(null)} width={680}
        footer={mine ? [<Button key="r" danger loading={busy} onClick={() => decide(false)}>Рекомендовать отклонить</Button>, <Button key="a" type="primary" loading={busy} onClick={() => decide(true)}>Рекомендовать принять</Button>] : null}>
        {cur && <div className="space-y-3">
          <AppealCard a={cur} />
          {mine && <>
            <Input.TextArea rows={3} placeholder="Обоснование решения (обязательно)" value={text} onChange={(e) => setText(e.target.value)} />
            {cur.score !== null && <div className="flex flex-wrap items-center gap-2">Новый итоговый балл (необязательно, только при принятии):
              <InputNumber min={0} max={cur.max_score} value={score} onChange={setScore} /> <span className="text-gray-500">сейчас {cur.score} / {cur.max_score}</span></div>}
            <Alert type="info" showIcon title="Ваше решение уйдёт администратору. Оценка изменится только после его подтверждения; первоначальная оценка сохранится." />
          </>}
          {cur.status === "teacher_done" && <Alert type="info" showIcon title="Ваше решение отправлено, ожидает подтверждения администратором." />}
        </div>}
      </Modal>
    </div>
  );
}
