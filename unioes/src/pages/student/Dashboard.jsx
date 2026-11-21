<<<<<<< HEAD
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Profile from "../Profile.jsx";
import { Navigate, Route, Routes, useNavigate, useParams } from "react-router";
import { App as AntApp, Alert, Button, Card, Checkbox, Dropdown, Empty, Form, Input, Modal, Progress, Radio, Select, Spin, Statistic, Table, Tag } from "antd";
import { MoreOutlined } from "@ant-design/icons";
import { api } from "../../api/client.js";
import { createAutosaver } from "../../api/autosave.js";
import { DIFFICULTY, EXAM_TYPE, fmtDate } from "../../components/common/constants.js";
import RichText from "../../components/common/RichText.jsx";

const STATE = {
  available: ["Доступен", "green"], upcoming: ["Скоро", "blue"], in_progress: ["В процессе", "orange"],
  completed: ["Завершён", "default"], closed: ["Закрыт", "red"],
};
const ATT = { waiting: ["Ожидает проверки", "orange"], final: ["Проверен", "green"] };
const APPEAL = { submitted: ["У администратора", "blue"], review: ["У преподавателя", "orange"], teacher_done: ["На проверке у администратора", "gold"], accepted: ["Принята", "green"], rejected: ["Отклонена", "red"] };
const CATS = [["wrong_question", "Некорректный вопрос"], ["wrong_answer", "Неверный ответ"], ["ambiguous", "Неоднозначная формулировка"], ["technical", "Технический сбой"], ["other", "Другое"]];

function useLoad(path) {
  const { message } = AntApp.useApp();
  const [data, setData] = useState(null);
  const load = useCallback(() => api(path).then(setData).catch((e) => { message.error(e.message); setData([]); }), [path, message]);
  useEffect(() => { load(); }, [load]);
  return [data, load];
}

function Home() {
  const [exams] = useLoad("/student/exams/");
  const [results] = useLoad("/student/results/");
  const nav = useNavigate();
  if (!exams || !results) return <Spin />;
  const done = results.filter((r) => r.score !== null);
  const avg = done.length ? Math.round(done.reduce((s, r) => s + r.percent, 0) / done.length) : 0;
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Главная</h1>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Card><Statistic title="Всего экзаменов" value={exams.length} /></Card>
        <Card><Statistic title="Пройдено" value={results.length} /></Card>
        <Card><Statistic title="Предстоит" value={exams.filter((e) => e.state === "upcoming" || e.state === "available").length} /></Card>
        <Card><Statistic title="Средний балл, %" value={avg} /></Card>
      </div>
      <Button type="primary" onClick={() => nav("/student/exams")}>К доступным экзаменам</Button>
    </div>
  );
}

function Exams() {
  const [rows] = useLoad("/student/exams/");
  const { message } = AntApp.useApp();
  const nav = useNavigate();
  if (!rows) return <Spin />;
  const start = async (e) => {
    try { const r = await api(`/student/exams/${e.id}/start/`, { method: "POST" }); nav(`/student/attempt/${r.attempt_id}`); }
    catch (err) { message.error(err.message); }
  };
  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold">Доступные экзамены</h1>
      {!rows.length && <Empty description="Для вашей группы нет опубликованных экзаменов" />}
      <div className="grid gap-3 md:grid-cols-2">
        {rows.map((e) => (
          <Card key={e.id} title={e.title} extra={<Tag color={STATE[e.state][1]}>{STATE[e.state][0]}</Tag>}>
            <p className="text-gray-500">{e.subject} · {e.teacher}</p>
            <div className="my-2 flex flex-wrap gap-2"><Tag color={EXAM_TYPE[e.exam_type].color}>{EXAM_TYPE[e.exam_type].label}</Tag><Tag>{e.questions} вопросов</Tag><Tag>{e.duration} мин</Tag></div>
            <p className="text-sm">{fmtDate(e.start_at)} — {fmtDate(e.end_at)}</p>
            <Button className="mt-3" type="primary" disabled={!["available", "in_progress"].includes(e.state)} onClick={() => start(e)}>
              {e.state === "in_progress" ? "Продолжить" : e.retry ? "Пройти ещё раз" : "Начать экзамен"}
            </Button>
          </Card>
        ))}
      </div>
    </div>
  );
}

function AppealModal({ open, onClose, attemptId, question, fixedCategory, questions = [], onDone }) {
  const { message } = AntApp.useApp();
  const [form] = Form.useForm();
  const submit = async (v) => {
    const { questions: picked, ...rest } = v;
    const body = { attempt: attemptId, ...rest, questions: fixedCategory ? (question ? [question.id] : []) : picked || [] };
    try { await api("/student/appeals/", { method: "POST", body }); message.success("Апелляция отправлена администратору"); form.resetFields(); onClose(); onDone?.(); }
    catch (e) { message.error(e.message); }
  };
  return (
    <Modal title="Подать апелляцию" open={open} onCancel={onClose} onOk={() => form.submit()} okText="Отправить апелляцию" cancelText="Отмена">
      {!fixedCategory && <Alert className="mb-3" type="warning" showIcon title="Апелляцию можно подать только один раз на экзамен — укажите в ней все спорные вопросы." />}
      <Form form={form} layout="vertical" onFinish={submit} initialValues={{ category: fixedCategory || "wrong_question" }}>
        {fixedCategory
          ? <Form.Item label="Вопрос"><Input disabled value={question ? `№ ${question.n}` : "Весь экзамен"} /></Form.Item>
          : <Form.Item name="questions" label="Спорные вопросы (можно несколько)"><Select mode="multiple" allowClear placeholder="Весь экзамен" optionFilterProp="label"
              options={questions.map((q) => ({ value: q.id, label: `№ ${q.n}. ${q.text.replace(/<[^>]+>/g, " ").slice(0, 80)}` }))} /></Form.Item>}
        <Form.Item name="category" label="Категория"><Select disabled={!!fixedCategory} options={CATS.map(([value, label]) => ({ value, label }))} /></Form.Item>
        <Form.Item name="text" label="Пояснение" rules={[{ required: true, message: "Опишите проблему" }]}><Input.TextArea rows={4} /></Form.Item>
      </Form>
    </Modal>
  );
}

const LEAVE = ["tab_hidden", "window_blur", "fullscreen_exit"];

/* Защита экзамена: полноэкранный режим, запрет копирования/печати, фиксация выходов со страницы.
   Браузер не позволяет сайту блокировать другие вкладки и программы, поэтому каждый выход фиксируется,
   а после лимита нарушений сервер завершает экзамен. */
function useExamGuard(attemptId, enabled, onTerminate) {
  const { message } = AntApp.useApp();
  const canFs = !!document.documentElement.requestFullscreen;
  const [inFs, setInFs] = useState(!canFs || !!document.fullscreenElement);
  const armed = useRef(false); // слежение начинается после входа в полноэкранный режим
  const last = useRef(0);

  const report = useCallback((kind) => {
    if (LEAVE.includes(kind)) { // blur + visibilitychange приходят вместе: считаем один раз
      const now = Date.now();
      if (now - last.current < 1500) return;
      last.current = now;
    }
    api(`/student/attempts/${attemptId}/event/`, { method: "POST", body: { kind } }).then((r) => {
      if (r.terminate) onTerminate();
      else if (LEAVE.includes(kind)) message.warning(`Нарушение ${r.violations} из ${r.max}. При превышении лимита экзамен будет завершён`, 6);
    }).catch(() => {});
  }, [attemptId, onTerminate, message]);

  useEffect(() => {
    if (!enabled) return undefined;
    const stop = (kind) => (e) => { e.preventDefault(); report(kind); };
    const onFs = () => {
      const on = !!document.fullscreenElement;
      setInFs(on);
      if (on) armed.current = true; else if (armed.current) report("fullscreen_exit");
    };
    const onVis = () => { if (document.hidden && armed.current) report("tab_hidden"); };
    const onBlur = () => { if (armed.current) report("window_blur"); };
    const onKey = (e) => {
      const k = e.key.toLowerCase();
      if ((e.ctrlKey || e.metaKey) && ["c", "x", "v", "a", "p", "s", "u"].includes(k)) stop(k === "v" ? "paste_attempt" : "copy_attempt")(e);
      else if (e.key === "F12" || e.key === "PrintScreen" || ((e.ctrlKey || e.metaKey) && e.shiftKey && ["i", "j", "c"].includes(k))) stop("devtools_key")(e);
    };
    const handlers = {
      copy: stop("copy_attempt"), cut: stop("copy_attempt"), paste: stop("paste_attempt"),
      contextmenu: stop("context_menu"), dragstart: (e) => e.preventDefault(), beforeprint: () => report("print_attempt"),
    };
    document.addEventListener("fullscreenchange", onFs);
    document.addEventListener("visibilitychange", onVis);
    window.addEventListener("blur", onBlur);
    document.addEventListener("keydown", onKey);
    Object.entries(handlers).forEach(([ev, h]) => document.addEventListener(ev, h));
    if (document.fullscreenElement) armed.current = true;
    return () => {
      armed.current = false; // снимаем слежение до выхода из полноэкранного режима
      document.removeEventListener("fullscreenchange", onFs);
      document.removeEventListener("visibilitychange", onVis);
      window.removeEventListener("blur", onBlur);
      document.removeEventListener("keydown", onKey);
      Object.entries(handlers).forEach(([ev, h]) => document.removeEventListener(ev, h));
      if (document.fullscreenElement) document.exitFullscreen?.().catch(() => {});
    };
  }, [enabled, report]);

  const enter = () => document.documentElement.requestFullscreen().catch(() => message.error("Браузер не разрешил полноэкранный режим"));
  const user = JSON.parse(localStorage.getItem("user") || sessionStorage.getItem("user") || "{}");
  const label = `${user.full_name || ""} ${user.student_id || ""}`.replace(/[<>&'"]/g, "");
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='340' height='170'><text x='10' y='100' font-size='18' font-family='sans-serif' fill='black' transform='rotate(-20 10 100)'>${label}</text></svg>`;
  const overlay = (
    <>
      {/* водяной знак: фото экрана можно связать со студентом */}
      <div aria-hidden className="pointer-events-none fixed inset-0 z-[1000]" style={{ opacity: 0.07, backgroundImage: `url("data:image/svg+xml,${encodeURIComponent(svg)}")` }} />
      <style>{"@media print { .exam-guard { display: none !important } body::before { content: 'Печать запрещена' } }"}</style>
      <Modal open={enabled && !inFs} closable={false} maskClosable={false} keyboard={false} footer={null} centered title="Экзамен проходит в полноэкранном режиме">
        <p className="mb-3">Не закрывайте полноэкранный режим и не переключайтесь на другие вкладки и программы: каждый выход фиксируется и виден преподавателю. После нескольких нарушений экзамен завершается автоматически. Копирование и печать отключены. Время продолжает идти.</p>
        <Button type="primary" block onClick={enter}>Перейти в полноэкранный режим</Button>
      </Modal>
    </>
  );
  return overlay;
}

function Take() {
  const { id } = useParams();
  const nav = useNavigate();
  const { message, modal } = AntApp.useApp();
  const [att, setAtt] = useState(null);
  const [i, setI] = useState(0);
  const [left, setLeft] = useState(0);
  const [ans, setAns] = useState({});
  const [appealQ, setAppealQ] = useState(null);
  const done = useRef(false);
  const [saveState, setSaveState] = useState("saved");
  const saver = useMemo(() => createAutosaver({
    send: (body) => api(`/student/attempts/${id}/answer/`, { method: "PUT", body }),
    onStatus: setSaveState,
  }), [id]);
  useEffect(() => () => saver.dispose(), [saver]);
  const guard = useExamGuard(id, !!att, useCallback(() => {
    done.current = true;
    message.error("Экзамен завершён: превышен лимит нарушений. Ответы сохранены");
    nav("/student/results", { replace: true });
  }, [nav, message]));

  const submit = useCallback(async () => {
    if (done.current) return;
    done.current = true;
    try {
      await saver.flush(); // дождаться всех автосохранений
      // snapshot уходит вместе со сдачей: если какой-то запрос не дошёл, ответ всё равно попадёт на сервер
      await api(`/student/attempts/${id}/submit/`, { method: "POST", body: { answers: saver.snapshot() } });
      nav("/student/results", { replace: true });
    } catch (e) { done.current = false; message.error(e.message); }
  }, [id, nav, message, saver]);

  useEffect(() => {
    api(`/student/attempts/${id}/`).then((a) => {
      if (a.status !== "in_progress") return nav("/student/results", { replace: true });
      setAtt(a); setLeft(a.remaining);
      setAns(Object.fromEntries(a.questions.map((q) => [q.id, { selected: q.selected, text: q.text_answer }])));
    }).catch((e) => message.error(e.message));
  }, [id, nav, message]);

  useEffect(() => {
    if (!att) return;
    const t = setInterval(() => setLeft((s) => s - 1), 1000);
    return () => clearInterval(t);
  }, [att]);
  useEffect(() => { if (att && left <= 0) submit(); }, [left, att, submit]);
  useEffect(() => { // предупреждение при закрытии страницы
    const h = (e) => { e.preventDefault(); e.returnValue = ""; };
    window.addEventListener("beforeunload", h);
    return () => window.removeEventListener("beforeunload", h);
  }, []);

  if (!att) return <Spin />;
  const q = att.questions[i];
  const cur = ans[q.id] || { selected: [], text: "" };
  const isAnswered = (x) => (ans[x.id]?.selected?.length || ans[x.id]?.text?.trim());
  const save = (v) => { // автосохранение при каждом изменении
    setAns((a) => ({ ...a, [q.id]: v }));
    saver.set(q.id, { selected: v.selected || [], text: v.text || "" }, { immediate: q.type !== "written" });
  };
  const mm = String(Math.max(0, Math.floor(left / 60))).padStart(2, "0"), ss = String(Math.max(0, left % 60)).padStart(2, "0");
  const answered = att.questions.filter(isAnswered).length;
  const confirm = () => modal.confirm({
    title: "Завершить экзамен?", content: `Отвечено ${answered} из ${att.questions.length}. После отправки изменить ответы нельзя.`,
    okText: "Отправить", cancelText: "Вернуться", onOk: submit,
  });

  return (
    <div className="exam-guard select-none space-y-3">
      {guard}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold">{att.title}</h1>
        <span>
          <Tag color={saveState === "error" ? "red" : saveState === "saving" ? "gold" : "green"}>
            {saveState === "error" ? "Ответы не сохраняются — проверьте сеть" : saveState === "saving" ? "Сохранение…" : "Сохранено"}
          </Tag>
          <Tag color={left < 300 ? "red" : "blue"} className="text-base">⏱ {mm}:{ss}</Tag>
        </span>
      </div>
      <Progress percent={Math.round((answered / att.questions.length) * 100)} size="small" />
      <div className="grid gap-3 md:grid-cols-[1fr_220px]">
        <Card
          title={`Вопрос ${i + 1} из ${att.questions.length}`}
          extra={<><Tag color={DIFFICULTY[q.difficulty].color}>{DIFFICULTY[q.difficulty].label}</Tag>
            {att.allow_appeals && <Dropdown trigger={["click"]} menu={{ items: [{ key: "p", label: "Сообщить о проблеме" }, { key: "a", label: "Подать апелляцию" }], onClick: ({ key }) => key === "p" ? setAppealQ({ id: q.id, n: i + 1 }) : message.info("Апелляцию по содержанию вопроса можно подать после завершения экзамена: раздел «Мои результаты»") }}><Button type="text" icon={<MoreOutlined />} aria-label="Меню вопроса" /></Dropdown>}</>}
        >
          <RichText className="mb-4" text={q.text} />
          {q.type === "single" && <Radio.Group className="flex flex-col gap-2" value={cur.selected[0]} onChange={(e) => save({ ...cur, selected: [e.target.value] })}>{q.options.map((o) => <Radio key={o.i} value={o.i}><RichText text={o.text} /></Radio>)}</Radio.Group>}
          {q.type === "multiple" && <Checkbox.Group className="flex flex-col gap-2" value={cur.selected} onChange={(v) => save({ ...cur, selected: v })} options={q.options.map((o) => ({ label: <RichText text={o.text} />, value: o.i }))} />}
          {q.type === "written" && <Input.TextArea className="select-text" rows={10} value={cur.text} placeholder="Введите развёрнутый ответ" onChange={(e) => save({ ...cur, text: e.target.value })} />}
          <div className="mt-4 flex justify-between">
            <Button disabled={i === 0} onClick={() => setI(i - 1)}>Назад</Button>
            {i < att.questions.length - 1 ? <Button type="primary" onClick={() => setI(i + 1)}>Далее</Button> : <Button type="primary" onClick={confirm}>Завершить</Button>}
          </div>
        </Card>
        <Card size="small" title="Навигация">
          <div className="flex flex-wrap gap-2">{att.questions.map((x, k) => <Button key={x.id} size="small" type={k === i ? "primary" : isAnswered(x) ? "default" : "dashed"} onClick={() => setI(k)}>{k + 1}</Button>)}</div>
          <Button block className="mt-3" danger onClick={confirm}>Завершить экзамен</Button>
        </Card>
      </div>
      <AppealModal open={!!appealQ} question={appealQ} attemptId={Number(id)} fixedCategory="technical" onClose={() => setAppealQ(null)} />
    </div>
  );
}

function Results() {
  const [rows, reload] = useLoad("/student/results/");
  const [open, setOpen] = useState(null);
  const [detail, setDetail] = useState(null);
  const [appealFor, setAppealFor] = useState(null);
  const [appealQs, setAppealQs] = useState([]);
  const startAppeal = (r) => { setAppealFor(r); api(`/student/results/${r.id}/`).then((d) => setAppealQs(d.questions || [])); };
  const show = (r) => { setOpen(r); api(`/student/results/${r.id}/`).then(setDetail); };
  if (!rows) return <Spin />;
  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold">Мои результаты</h1>
      <Table rowKey="id" dataSource={rows} locale={{ emptyText: <Empty description="Результатов пока нет" /> }} scroll={{ x: true }} columns={[
        { title: "Экзамен", dataIndex: "exam_title" }, { title: "Предмет", dataIndex: "subject" },
        { title: "Дата", dataIndex: "date", render: fmtDate },
        { title: "Балл", render: (_, r) => (r.score === null ? "—" : `${r.score} / ${r.max_score}`) },
        { title: "%", dataIndex: "percent", render: (v) => v ?? "—" }, { title: "Оценка", dataIndex: "grade", render: (v) => v ?? "—" },
        { title: "Статус", dataIndex: "status", render: (s, r) => (r.hidden ? <Tag color="blue">Ожидает публикации</Tag> : <Tag color={ATT[s][1]}>{ATT[s][0]}</Tag>) },
        { title: "", render: (_, r) => <div className="flex gap-2"><Button size="small" onClick={() => show(r)}>Подробнее</Button><Button size="small" disabled={r.appealed || !r.allow_appeals} onClick={() => startAppeal(r)}>{r.appealed ? "Апелляция подана" : "Апелляция"}</Button></div> },
      ]} />
      <Modal open={!!open} footer={null} width={720} onCancel={() => { setOpen(null); setDetail(null); }} title={open?.exam_title}>
        {!detail ? <Spin /> : detail.hidden ? <Alert message="Результат будет доступен после публикации преподавателем" type="info" /> : detail.status !== "final" ? <Alert message="Ожидает проверки преподавателем" type="warning" /> : <>
          {detail.original_score !== null && <Alert className="mb-2" type="info" message={`Результат пересмотрен по апелляции. Первоначальный балл: ${detail.original_score}`} />}
          <Table size="small" rowKey="question" pagination={false} dataSource={detail.answers} columns={[
            { title: "Вопрос", dataIndex: "question" }, { title: "Баллы", render: (_, a) => `${a.points ?? 0} / ${a.max}` }, { title: "Комментарий", dataIndex: "feedback" }]} />
        </>}
      </Modal>
      <AppealModal open={!!appealFor} questions={appealQs} attemptId={appealFor?.id} onClose={() => setAppealFor(null)} onDone={reload} />
    </div>
  );
}

function Appeals() {
  const [rows] = useLoad("/student/appeals/");
  if (!rows) return <Spin />;
  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold">Мои апелляции</h1>
      <Table rowKey="id" dataSource={rows} locale={{ emptyText: <Empty description="Вы ещё не подавали апелляций" /> }} scroll={{ x: true }} columns={[
        { title: "Экзамен", dataIndex: "exam" }, { title: "Вопросы", dataIndex: "questions", render: (v) => (v?.length ? v.map((n) => `№${n}`).join(", ") : "весь экзамен") },
        { title: "Категория", dataIndex: "category", render: (c) => CATS.find(([k]) => k === c)?.[1] || c },
        { title: "Причина", dataIndex: "text" }, { title: "Подана", dataIndex: "created_at", render: fmtDate },
        { title: "Статус", dataIndex: "status", render: (s) => <Tag color={APPEAL[s][1]}>{APPEAL[s][0]}</Tag> },
        { title: "Решение", dataIndex: "decision", render: (v) => v || "—" }]} />
    </div>
  );
}

export default function StudentDashboard() {
  return (
    <AntApp>
      <Routes>
        <Route index element={<Home />} />
        <Route path="dashboard" element={<Home />} />
        <Route path="exams" element={<Exams />} />
        <Route path="attempt/:id" element={<Take />} />
        <Route path="results" element={<Results />} />
        <Route path="appeals" element={<Appeals />} />
        <Route path="profile" element={<Profile />} />
        <Route path="*" element={<Navigate to="/student" replace />} />
      </Routes>
    </AntApp>
  );
}
=======
import React from 'react'

const Dashboard = () => {
  return (
	<div className='p-4 bg-white'>Dashboard</div>
  )
}

export default Dashboard
>>>>>>> a76c1519b266e317dfa05201d78f67214b4b70dc
