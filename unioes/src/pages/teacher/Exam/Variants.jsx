import { useCallback, useEffect, useState } from "react";
import { App, Alert, Button, Card, InputNumber, Popconfirm, Space, Switch, Table, Tag } from "antd";
import { api } from "../../../api/client.js";
import { DIFFICULTY } from "../../../components/common/constants.js";

const LEVELS = ["easy", "medium", "hard"];

// Генерация вариантов: каждому студенту выбранных групп — свой набор вопросов из банка
export default function Variants({ exam, locked, questions, onChanged }) {
  const { message, modal } = App.useApp();
  const [info, setInfo] = useState(null);
  const [cfg, setCfg] = useState({ easy: 0, medium: 0, hard: 0 });
  const [unique, setUnique] = useState(true);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  const load = useCallback(() => api(`/exams/${exam.id}/variants/`).then((d) => {
    setInfo(d);
    if (d.enabled) { setCfg({ easy: 0, medium: 0, hard: 0, ...d.config }); setUnique(d.unique); }
  }).catch((e) => message.error(e.message)), [exam.id, message]);
  // questions в зависимости: после изменения банка (импорт, удаление) варианты сбрасываются на сервере
  useEffect(() => { load(); }, [load, questions.length]);

  if (!info) return null;
  const perVariant = LEVELS.reduce((s, l) => s + (cfg[l] || 0), 0);
  const need = (l) => (cfg[l] || 0) * info.students_total;

  const generate = async () => {
    setBusy(true);
    setResult(null);
    try {
      const r = await api(`/exams/${exam.id}/variants/`, { method: "POST", body: { config: cfg, unique } });
      setResult(r);
      message.success("Варианты сформированы");
      load();
      onChanged?.();
    } catch (e) {
      if (e.data?.problems) modal.warning({ title: e.data.detail, content: <ul className="m-0 pl-4">{e.data.problems.map((p) => <li key={p}>{p}</li>)}</ul> });
      else message.error(e.message);
    } finally { setBusy(false); }
  };

  const disable = async () => {
    try { await api(`/exams/${exam.id}/variants/`, { method: "DELETE" }); setResult(null); load(); onChanged?.(); }
    catch (e) { message.error(e.message); }
  };

  return (
    <Card variant="borderless" title="Варианты для студентов"
      extra={info.enabled && <Tag color="green">Включены</Tag>}>
      <div className="space-y-3">
        <p className="m-0 text-slate-600">
          Выберите, сколько вопросов каждого уровня попадёт в один вариант. Банк — все вопросы выше;
          студентов в выбранных группах: <b>{info.students_total}</b>.
        </p>
        <div className="grid gap-3 sm:grid-cols-3">
          {LEVELS.map((l) => (
            <div key={l} className="rounded-lg border border-slate-200 p-3">
              <div style={{ color: DIFFICULTY[l].color }} className="font-semibold">{DIFFICULTY[l].label}</div>
              <InputNumber min={0} max={500} value={cfg[l]} disabled={locked} onChange={(v) => setCfg({ ...cfg, [l]: v ?? 0 })} addonAfter="в варианте" />
              <div className="mt-1 text-xs text-slate-500">В банке: {info.pool[l]}. {unique && cfg[l] > 0 && <>Чтобы не повторялись: {need(l)}{need(l) > info.pool[l] ? <span className="text-amber-600"> — не хватает {need(l) - info.pool[l]}</span> : " — хватает"}</>}</div>
            </div>
          ))}
        </div>
        <Space wrap>
          <Switch checked={unique} disabled={locked} onChange={setUnique} />
          <span>Вопросы не должны повторяться у разных студентов</span>
        </Space>
        <div className="text-sm text-slate-500">Вопросов в варианте: <b>{perVariant}</b>. Сумма баллов варианта должна равняться максимальному баллу ({exam.max_score}); баллы внутри одного уровня должны быть одинаковыми.</div>
        <Space wrap>
          <Button type="primary" loading={busy} disabled={locked || perVariant === 0} onClick={generate}>
            {info.enabled ? "Сформировать заново" : "Сформировать варианты"}
          </Button>
          {info.enabled && <Popconfirm title="Отключить варианты?" description="Все студенты снова получат весь банк вопросов." okText="Отключить" cancelText="Отмена" onConfirm={disable} disabled={locked}>
            <Button disabled={locked}>Отключить варианты</Button>
          </Popconfirm>}
        </Space>
        {locked && <Alert type="info" showIcon title="Экзамен опубликован или в архиве: чтобы изменить варианты, скройте экзамен." />}
        {result?.warning && <Alert type="warning" showIcon title={result.warning} />}
        {info.enabled && info.stats && (
          <Alert type={info.stats.fully_unique || !info.unique ? "success" : "warning"} showIcon
            title={info.stats.fully_unique ? "Общих вопросов между студентами нет" : `Вопросов, которые попались нескольким студентам: ${info.stats.repeated_questions}`}
            description={`Вариантов: ${info.stats.students}, использовано вопросов из банка: ${info.stats.questions_used}. Студент, добавленный в группу позже, получит свой вариант при первом входе на экзамен.`} />
        )}
        {info.enabled && info.variants.length > 0 && (
          <Table size="small" rowKey={(r) => r.student + r.group} dataSource={info.variants} pagination={{ pageSize: 10, hideOnSinglePage: true }}
            columns={[{ title: "Студент", dataIndex: "student" }, { title: "Группа", dataIndex: "group" }, { title: "Вопросов", dataIndex: "questions" },
              { title: "Номера вопросов в банке", dataIndex: "question_ids", render: (v) => <span className="text-xs text-slate-500">{v.join(", ")}</span> }]} />
        )}
      </div>
    </Card>
  );
}
