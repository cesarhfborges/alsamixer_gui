import threading
import time
import unittest
from unittest import mock

from src.core.settings import AppSettings, InMemorySettingsRepository
from src.gui.window_placement import Monitor, choose_position, parse_geometry, parse_xrandr_monitors
from tests.test_gui import HAS_DISPLAY, FakeController

XRANDR = """Monitors: 3
 0: +*DP-0 1920/527x1080/296+1920+0  DP-0
 1: +DP-4 1920/527x1080/296+3840+0  DP-4
 2: +DP-2 1920/531x1080/299+0+0  DP-2
"""
MONITORS = parse_xrandr_monitors(XRANDR)


class WindowPlacementTest(unittest.TestCase):
    def test_parse_xrandr(self):
        self.assertEqual(len(MONITORS), 3)
        self.assertEqual(MONITORS[0], Monitor("DP-0", 1920, 0, 1920, 1080, primary=True))
        self.assertFalse(MONITORS[2].primary)

    def test_parse_geometry(self):
        self.assertEqual(parse_geometry("960x620+100+50"), (960, 620, 100, 50))
        self.assertEqual(parse_geometry("960x620"), (960, 620, None, None))
        self.assertEqual(parse_geometry("960x620+-8+20"), (960, 620, -8, 20))
        self.assertEqual(parse_geometry(None), (None, None, None, None))
        self.assertEqual(parse_geometry("lixo"), (None, None, None, None))

    def test_saved_position_is_kept_when_visible(self):
        self.assertEqual(choose_position(960, 620, (4000, 100), MONITORS), (4000, 100))

    def test_without_saved_position_centers_on_primary(self):
        self.assertEqual(choose_position(960, 620, (None, None), MONITORS), (1920 + 480, 230))

    def test_position_on_disconnected_monitor_falls_back_to_primary(self):
        self.assertEqual(choose_position(960, 620, (6000, 100), MONITORS), (2400, 230))

    def test_no_monitor_info_lets_window_manager_decide(self):
        self.assertIsNone(choose_position(960, 620, (None, None), []))


class DispatcherAndInstanceTest(unittest.TestCase):
    def test_single_instance(self):
        from src.gui.single_instance import SingleInstance
        first = SingleInstance(name=f"alsamixer-gui-test-{time.time()}")
        received = threading.Event()
        first.on_message = lambda message: received.set()
        self.assertTrue(first.acquire())
        second = SingleInstance(name=first.address[1:].rsplit("-", 1)[0])
        self.assertFalse(second.acquire())  # já existe: avisa a primeira
        self.assertTrue(received.wait(2))
        first.release()


if __name__ == "__main__":
    unittest.main()


class XorgRightClickTest(unittest.TestCase):
    def test_right_click_posts_menu_and_left_click_keeps_default(self):
        import types
        from src.gui.tray import PystrayTrayIcon

        class BaseIcon:
            HAS_MENU = False
            def __init__(self, *a): self.activated = 0
            def _on_button_press(self, event): self.activated += 1

        fake_pystray = types.SimpleNamespace(Icon=BaseIcon)
        opened = []
        tray = PystrayTrayIcon(fake_pystray, lambda: None, lambda: None, post=lambda f: f(),
                               on_menu=lambda x, y: opened.append((x, y)))
        icon = tray._icon_class()()
        icon._on_button_press(types.SimpleNamespace(detail=3, root_x=10, root_y=20))
        icon._on_button_press(types.SimpleNamespace(detail=1, root_x=0, root_y=0))
        self.assertEqual(opened, [(10, 20)])
        self.assertEqual(icon.activated, 1)
