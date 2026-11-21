// Разбор текста вопроса на обычный текст и блоки кода
const CODE = /<code(?:\s+lang=["']?([\w+#.-]{1,20})["']?)?\s*>([\s\S]*?)<\/code>/gi;

// Формулы LaTeX вне блоков кода: $...$ (в строке), $$...$$ (отдельной строкой), \$ — обычный знак доллара
export function parseMath(text) {
  const out = [];
  let buf = "";
  const flush = () => { if (buf) out.push({ type: "text", value: buf }); buf = ""; };
  for (let i = 0; i < text.length; ) {
    const c = text[i];
    if (c === "\\" && text[i + 1] === "$") { buf += "$"; i += 2; continue; }
    if (c === "$") {
      const display = text[i + 1] === "$";
      const open = display ? 2 : 1;
      let j = i + open;
      let end = -1;
      for (; j < text.length; j++) {
        if (text[j] === "\\") { j++; continue; }
        if (text[j] === "$" && (!display || text[j + 1] === "$")) { end = j; break; }
        if (!display && text[j] === "\n") break; // $...$ не переходит на новую строку
      }
      const tex = end > i + open ? text.slice(i + open, end) : "";
      if (end > -1 && tex.trim()) {
        flush();
        out.push({ type: "math", display, value: tex.trim() });
        i = end + open;
        continue;
      }
    }
    buf += c;
    i++;
  }
  flush();
  return out;
}

export function parseRich(text) {
  text = String(text ?? "");
  const parts = [];
  let last = 0;
  const plain = (s) => parts.push(...parseMath(s));
  for (const m of text.matchAll(CODE)) {
    if (m.index > last) plain(text.slice(last, m.index));
    parts.push({ type: "code", lang: m[1] || "", value: m[2].replace(/^\r?\n/, "").replace(/\s+$/, "") });
    last = m.index + m[0].length;
  }
  if (last < text.length) plain(text.slice(last));
  return parts;
}

// Кнопки быстрой вставки формул в редакторе: [подпись, шаблон]
export const MATH_SNIPPETS = [
  ["$ $", "$x$"], ["Дробь", "$\\frac{a}{b}$"], ["Степень", "$x^{2}$"], ["Индекс", "$x_{i}$"],
  ["Корень", "$\\sqrt{x}$"], ["Сумма", "$$\\sum_{i=1}^{n} i$$"], ["Интеграл", "$$\\int_{a}^{b} f(x)\\,dx$$"],
  ["Предел", "$$\\lim_{x \\to 0} \\frac{\\sin x}{x} = 1$$"],
];

// Вставка шаблона блока кода в текстовое поле (для редактора вопросов)
export const CODE_TEMPLATE = (lang = "python") => `\n<code lang=${lang}>\n\n</code>\n`;
