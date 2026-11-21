// Автосохранение ответов: debounce, один запрос на вопрос за раз, повтор при сбое, метка времени ts.
// Сервер не принимает ответ с ts меньше уже сохранённого, поэтому порядок доставки не важен.
export function createAutosaver({ send, onStatus = () => {}, debounceMs = 600, retries = 4, backoffMs = 800, clock = Date.now }) {
  const state = new Map(); // questionId -> { value, ts, timer, running, dirty }
  let seq = 0;

  const status = () => {
    const bad = [...state.values()].some((s) => s.failed);
    const busy = [...state.values()].some((s) => s.dirty || s.running);
    onStatus(bad ? "error" : busy ? "saving" : "saved");
  };

  async function run(qid) {
    const s = state.get(qid);
    if (s.running) return;
    s.running = true;
    try {
      while (s.dirty) {
        const { value, ts } = s;
        s.dirty = false;
        let ok = false;
        for (let k = 0; k <= retries && !ok; k++) {
          try {
            await send({ question: qid, ...value, ts });
            ok = true;
          } catch (e) {
            if (e?.status >= 400 && e?.status < 500 && e.status !== 429) break; // повтор бессмыслен
            await new Promise((r) => setTimeout(r, backoffMs * 2 ** k));
          }
        }
        s.failed = !ok;
        if (!ok && !s.dirty) { s.dirty = true; s.failedValue = true; break; } // оставим «грязным» для flush
      }
    } finally {
      s.running = false;
      status();
    }
  }

  return {
    // монотонный ts: даже в одну миллисекунду значения различаются
    set(qid, value, { immediate = false } = {}) {
      const s = state.get(qid) || {};
      s.value = value; s.ts = Math.max(clock(), (s.ts || 0) + 1 + 0 * seq++); s.dirty = true;
      state.set(qid, s);
      clearTimeout(s.timer);
      s.timer = setTimeout(() => run(qid), immediate ? 0 : debounceMs);
      status();
    },
    // дождаться отправки всего, что накоплено (перед сдачей)
    async flush() {
      await Promise.all([...state.entries()].map(async ([qid, s]) => {
        clearTimeout(s.timer);
        s.failed = false;
        if (s.dirty) await run(qid);
        while (s.running) await new Promise((r) => setTimeout(r, 20));
      }));
      status();
    },
    // все ответы одним списком — уходит вместе со сдачей как страховка
    snapshot() {
      return [...state.entries()].filter(([, s]) => s.value).map(([qid, s]) => ({ question: qid, ...s.value, ts: s.ts }));
    },
    pending: () => [...state.values()].some((s) => s.dirty || s.running),
    dispose: () => state.forEach((s) => clearTimeout(s.timer)),
  };
}
