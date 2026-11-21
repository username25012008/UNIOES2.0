import { Navigate, Route, Routes } from "react-router";
import Profile from "../Profile.jsx";
import { App as AntApp } from "antd";

import Overview from "./Exam/Overview.jsx";
import MyExams from "./Exam/MyExams.jsx";
import ExamForm from "./Exam/ExamsForm.jsx";
import Questions from "./Exam/Questions.jsx";
import Grading from "./Grading.jsx";
import Results from "./Results.jsx";
import TeacherAppeals from "./Appeals.jsx";

// Контейнер раздела /teacher/* — здесь вложенные маршруты учителя
export default function TeacherDashboard() {
  return (
    <AntApp>
      <Routes>
        <Route path="/" index element={<Overview />} />
        <Route path="/dashboard" index element={<Overview />} />
        <Route path="exams" element={<MyExams />} />
        <Route path="exams/new" element={<ExamForm />} />
        <Route path="exams/:id/edit" element={<ExamForm />} />
        <Route path="exams/:id/questions" element={<Questions />} />
        <Route path="grading" element={<Grading />} />
        <Route path="results" element={<Results />} />
        <Route path="appeals" element={<TeacherAppeals />} />
        <Route path="profile" element={<Profile />} />
        <Route path="*" element={<Navigate to="/teacher" replace />} />
      </Routes>
    </AntApp>
  );
}
