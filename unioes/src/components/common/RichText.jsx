// Текст вопроса: обычный текст, блоки кода <code lang=python> … </code> и формулы $…$ / $$…$$.
// Код и текст выводятся как текстовые узлы React; HTML формулы создаёт KaTeX (trust: false).
import katex from "katex";
import "katex/dist/katex.min.css";
import { parseRich } from "./richtext.js";

// KaTeX сам экранирует вход (trust: false), ошибки в формуле показывает красным, а не падает
const tex = (src, display) =>
  katex.renderToString(src, { displayMode: display, throwOnError: false, trust: false, strict: "ignore", maxExpand: 1000, output: "html" });

export default function RichText({ text, className = "" }) {
  return (
    <div className={className}>
      {parseRich(text).map((p, i) =>
        p.type === "code" ? (
          <figure key={i} className="my-2 overflow-hidden rounded-lg bg-slate-900 text-slate-100">
            {p.lang && <figcaption className="bg-slate-800 px-3 py-1 text-xs uppercase tracking-wide text-slate-400">{p.lang}</figcaption>}
            <pre className="m-0 overflow-x-auto p-3 text-sm leading-relaxed"><code>{p.value}</code></pre>
          </figure>
        ) : p.type === "math" ? (
          <span key={i} className={p.display ? "my-2 block overflow-x-auto" : ""} dangerouslySetInnerHTML={{ __html: tex(p.value, p.display) }} />
        ) : (
          <span key={i} className="whitespace-pre-wrap">{p.value}</span>
        )
      )}
    </div>
  );
}
