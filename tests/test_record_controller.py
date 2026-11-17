"""RecordController 状态机冒烟测试。"""
import tempfile
import unittest

from app.controllers.record_controller import RecordController
from app.infra.events import EventBus


class TestRecordControllerState(unittest.TestCase):
    def test_initial_state_idle(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = RecordController(EventBus(), tmp)
            self.assertEqual(rc.state, "idle")

    def test_stop_without_start_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = RecordController(EventBus(), tmp)
            with self.assertRaises(RuntimeError):
                rc.stop()

    def test_double_stop_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = RecordController(EventBus(), tmp)
            # 直接调用 stop 会抛异常（因为状态是 idle）
            with self.assertRaises(RuntimeError):
                rc.stop()
            with self.assertRaises(RuntimeError):
                rc.stop()


if __name__ == "__main__":
    unittest.main(verbosity=2)