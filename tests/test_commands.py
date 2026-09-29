from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from line_project_manager import CommandProcessor, Database, TaskService


ALICE = "U_EXAMPLE_ALICE"
BOB = "U_EXAMPLE_BOB"


class CommandProcessorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        database = Database(Path(self.temporary.name) / "tasks.sqlite3")
        database.initialize_default()
        self.service = TaskService(database)
        self.service.register_member(ALICE, "Alice", ["admin"])
        self.service.register_member(BOB, "Bob", ["contributor"])
        self.service.register_member("U_EXAMPLE_CAROL", "Carol", ["contributor"])
        self.processor = CommandProcessor(self.service)
        self.reference = datetime(2026, 10, 1, 9, 0, tzinfo=ZoneInfo("Asia/Tokyo"))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def handle(self, text: str, actor: str = ALICE):
        return self.processor.handle(text, actor_id=actor, reference=self.reference)

    def test_create_for_self_with_due_date(self) -> None:
        result = self.handle("新增任务“演示任务”，由我负责，截止10月15日")
        self.assertTrue(result.handled)
        self.assertIn("TASK-0001", result.text)
        task = self.service.get_task("TASK-0001")
        self.assertEqual(task["owner_id"], ALICE)
        self.assertEqual(task["due_at"], "2026-10-15T18:00:00+09:00")

    def test_create_without_comma_stops_name_before_owner(self) -> None:
        result = self.handle("新增任务“演示任务”由我负责")
        self.assertIn("TASK-0001", result.text)
        self.assertEqual(self.service.get_task("TASK-0001")["name"], "演示任务")

    def test_invalid_date_returns_helpful_reply(self) -> None:
        result = self.handle("新增任务“演示任务”，由我负责，截止2月30日")
        self.assertIn("截止时间无效", result.text)
        self.assertEqual(self.service.list_tasks(), [])

    def test_short_date_rolls_into_next_year_when_needed(self) -> None:
        reference = datetime(2026, 12, 31, 9, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
        result = self.processor.handle(
            "新增任务“跨年任务”，由我负责，截止1月2日",
            actor_id=ALICE,
            reference=reference,
        )
        self.assertIn("TASK-0001", result.text)
        self.assertEqual(
            self.service.get_task("TASK-0001")["due_at"],
            "2027-01-02T18:00:00+09:00",
        )

    def test_create_for_registered_member_and_update_stage(self) -> None:
        created = self.handle("创建任务“示例检查”，负责人是Bob，截止2026-10-20 16:30")
        self.assertIn("负责人：Bob", created.text)
        updated = self.handle("更新 TASK-0001，阶段改为审核")
        self.assertIn("阶段：审核", updated.text)

    def test_complete_cancel_and_query(self) -> None:
        self.handle("新增任务“任务一”，由我负责")
        listing = self.handle("查询当前任务")
        self.assertIn("任务一", listing.text)
        completed = self.handle("TASK-0001 已完成")
        self.assertIn("状态：已完成", completed.text)
        self.assertIn("当前没有", self.handle("查询任务").text)

        self.handle("新增任务“任务二”，由我负责")
        cancelled = self.handle("取消 TASK-0002")
        self.assertIn("状态：已取消", cancelled.text)

    def test_unknown_member_and_unrelated_text(self) -> None:
        unknown = self.handle("查询任务", actor="U_EXAMPLE_UNKNOWN")
        self.assertIn("还不是已登记", unknown.text)
        self.assertFalse(self.handle("今天天气很好").handled)

    def test_unrelated_member_cannot_modify_task(self) -> None:
        self.handle("新增任务“任务一”，由我负责")
        result = self.handle("TASK-0001 已完成", actor="U_EXAMPLE_CAROL")
        self.assertIn("没有权限", result.text)
        self.assertEqual(self.service.get_task("TASK-0001")["status"], "open")

    def test_long_task_list_stays_within_one_line_message_limit(self) -> None:
        for index in range(30):
            self.service.create_task(
                name=f"任务{index}-" + "示例" * 70,
                created_by=ALICE,
                owner_id=ALICE,
            )
        result = self.handle("查询任务")
        self.assertLessEqual(len(result.text), 5000)
        self.assertIn("未显示", result.text)


if __name__ == "__main__":
    unittest.main()
