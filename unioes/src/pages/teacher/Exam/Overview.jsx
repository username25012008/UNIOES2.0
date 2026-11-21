import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { Alert, Button, Card, Col, Empty, List, Row, Skeleton, Statistic, Tag } from "antd";
import {
  FileTextOutlined,
  CheckCircleOutlined,
  EditOutlined,
  TeamOutlined,
  PlusOutlined,
} from "@ant-design/icons";

import { api } from "../../../api/client.js";
import { EXAM_TYPE, fmtDate } from "../../../components/common/constants.js";

export default function Overview() {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/teacher/stats/")
      .then(setStats)
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <Alert type="error" showIcon title={error} />;
  if (!stats) return <Skeleton active paragraph={{ rows: 6 }} />;

  const cards = [
    { title: "Всего экзаменов", value: stats.total_exams, icon: <FileTextOutlined /> },
    { title: "Опубликовано", value: stats.published, icon: <CheckCircleOutlined /> },
    { title: "Черновики", value: stats.draft, icon: <EditOutlined /> },
    { title: "Студентов в группах", value: stats.total_students, icon: <TeamOutlined /> },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900 m-0">Панель учителя</h1>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/teacher/exams/new")}>
          Создать экзамен
        </Button>
      </div>

      <Row gutter={[16, 16]}>
        {cards.map((c) => (
          <Col xs={24} sm={12} lg={6} key={c.title}>
            <Card variant="borderless">
              <Statistic title={c.title} value={c.value} prefix={c.icon} />
            </Card>
          </Col>
        ))}
      </Row>

      <Card variant="borderless" title="Ближайшие экзамены">
        {stats.upcoming.length === 0 ? (
          <Empty description="Нет запланированных опубликованных экзаменов" />
        ) : (
          <List
            dataSource={stats.upcoming}
            renderItem={(e) => (
              <List.Item
                actions={[
                  <Button key="o" type="link" onClick={() => navigate(`/teacher/exams/${e.id}/questions`)}>
                    Открыть
                  </Button>,
                ]}
              >
                <List.Item.Meta
                  title={
                    <>
                      {e.title} <Tag color={EXAM_TYPE[e.exam_type].color}>{EXAM_TYPE[e.exam_type].label}</Tag>
                    </>
                  }
                  description={`${e.subject} · ${e.group_names.join(", ")} · ${fmtDate(e.start_at)}`}
                />
              </List.Item>
            )}
          />
        )}
      </Card>
    </div>
  );
}
