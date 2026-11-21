import { Navigate, Route, Routes } from "react-router";
<<<<<<< HEAD
import Profile from "../Profile.jsx";
=======
>>>>>>> a76c1519b266e317dfa05201d78f67214b4b70dc
import { App as AntApp } from "antd";

import Overview from "./Exam/Overview.jsx";
import MyExams from "./Exam/MyExams.jsx";
import ExamForm from "./Exam/ExamsForm.jsx";
import Questions from "./Exam/Questions.jsx";
<<<<<<< HEAD
import Grading from "./Grading.jsx";
import Results from "./Results.jsx";
import TeacherAppeals from "./Appeals.jsx";
=======
>>>>>>> a76c1519b266e317dfa05201d78f67214b4b70dc

// Контейнер раздела /teacher/* — здесь вложенные маршруты учителя
export default function TeacherDashboard() {
  return (
    <AntApp>
      <Routes>
<<<<<<< HEAD
        <Route path="/" index element={<Overview />} />
        <Route path="/dashboard" index element={<Overview />} />
=======
        <Route index element={<Overview />} />
>>>>>>> a76c1519b266e317dfa05201d78f67214b4b70dc
        <Route path="exams" element={<MyExams />} />
        <Route path="exams/new" element={<ExamForm />} />
        <Route path="exams/:id/edit" element={<ExamForm />} />
        <Route path="exams/:id/questions" element={<Questions />} />
<<<<<<< HEAD
        <Route path="grading" element={<Grading />} />
        <Route path="results" element={<Results />} />
        <Route path="appeals" element={<TeacherAppeals />} />
        <Route path="profile" element={<Profile />} />
=======
>>>>>>> a76c1519b266e317dfa05201d78f67214b4b70dc
        <Route path="*" element={<Navigate to="/teacher" replace />} />
      </Routes>
    </AntApp>
  );
}
