import dayjs from "dayjs";

export const STATUS = {
  draft: { label: "Черновик", color: "default" },
  published: { label: "Опубликован", color: "success" },
  hidden: { label: "Скрыт", color: "warning" },
  archived: { label: "В архиве", color: "purple" },
};

export const EXAM_TYPE = {
  test: { label: "Тест", color: "blue" },
  written: { label: "Письменный", color: "geekblue" },
};

export const DIFFICULTY = {
  easy: { label: "Лёгкий", color: "#16a34a" },
  medium: { label: "Средний", color: "#d97706" },
  hard: { label: "Сложный", color: "#dc2626" },
};

export const QUESTION_TYPE = {
  single: "Один ответ",
  multiple: "Несколько ответов",
  written: "Развёрнутый ответ",
};

export const fmtDate = (v) => (v ? dayjs(v).format("DD.MM.YYYY HH:mm") : "—");
