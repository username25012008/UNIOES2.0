import { Tag } from "antd";
import RichText from "./RichText.jsx";
import { APPEAL_CATS } from "./constants.js";

// Общая карточка апелляции для админа и преподавателя
export default function AppealCard({ a, showTeacher = true }) {
  return (
    <div className="space-y-2">
      <p className="m-0"><b>{a.student}</b> ({a.group}) · {a.exam} · преподаватель: {a.teacher}</p>
      <p className="m-0 text-sm text-slate-500">
        Категория: {APPEAL_CATS[a.category] || a.category} · оценка: {a.score ?? "—"} / {a.max_score}
      </p>
      {a.questions?.length > 0 && a.questions.map((q) => (
        <div key={q.n} className="rounded bg-slate-50 p-2 text-sm"><b>Вопрос № {q.n}</b><RichText text={q.text} /></div>
      ))}
      <p className="m-0 whitespace-pre-wrap">{a.text}</p>
      {a.admin_note && <p className="m-0 rounded bg-blue-50 p-2 text-sm">Комментарий администратора: {a.admin_note}</p>}
      {showTeacher && a.teacher_accept !== null && a.teacher_accept !== undefined && (
        <div className="rounded bg-amber-50 p-2 text-sm">
          <Tag color={a.teacher_accept ? "green" : "red"}>Преподаватель: {a.teacher_accept ? "принять" : "отклонить"}</Tag>
          {a.teacher_new_score != null && <span>новый балл: <b>{a.teacher_new_score}</b> (сейчас {a.score})</span>}
          <div className="whitespace-pre-wrap">{a.teacher_note}</div>
        </div>
      )}
      {a.decision && <p className="m-0 rounded bg-slate-100 p-2 text-sm">Итоговый ответ студенту: {a.decision}</p>}
    </div>
  );
}
