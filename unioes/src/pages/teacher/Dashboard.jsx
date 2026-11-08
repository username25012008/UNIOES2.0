import { Navigate, Route, Routes } from "react-router";
import { App as AntApp } from "antd";

import Overview from "./Exam/Overview.jsx";
import MyExams from "./Exam/MyExams.jsx";
import ExamForm from "./Exam/ExamsForm.jsx";
import Questions from "./Exam/Questions.jsx";

// Контейнер раздела /teacher/* — здесь вложенные маршруты учителя
export default function TeacherDashboard() {
  return (
    <AntApp>
      <Routes>
        <Route index element={<Overview />} />
        <Route path="exams" element={<MyExams />} />
        <Route path="exams/new" element={<ExamForm />} />
        <Route path="exams/:id/edit" element={<ExamForm />} />
        <Route path="exams/:id/questions" element={<Questions />} />
        <Route path="*" element={<Navigate to="/teacher" replace />} />
      </Routes>
    </AntApp>
  );
}
