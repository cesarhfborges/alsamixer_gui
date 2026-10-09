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


class FakeTray:
    def __init__(self, available=True, **callbacks):
        self.available = available
        self.running = False
        self.callbacks = callbacks

    def start(self):
        if self.available:
            self.running = True

    def stop(self):
        self.running = False


@unittest.skipUnless(HAS_DISPLAY, "requer servidor gráfico")
class TrayBehaviourTest(unittest.TestCase):
    def make_app(self, available=True, **settings):
        from src.gui.main_window import AlsamixerGUI
        self.repo = InMemorySettingsRepository(AppSettings(poll_interval_ms=0, theme="Dark", **settings))
        self.trays = []

        def factory(**callbacks):
            tray = FakeTray(available, **callbacks)
            self.trays.append(tray)
            return tray

        app = AlsamixerGUI(FakeController(), settings_repository=self.repo, tray_factory=factory)
        self.destroyed = False
        original_destroy = app.destroy

        def destroy():
            self.destroyed = True
            original_destroy()
        app.destroy = destroy
        self.addCleanup(lambda: None if self.destroyed else original_destroy())
        app.update()
        return app

    def test_close_without_tray_quits(self):
        app = self.make_app()
        app.close()
        self.assertTrue(self.destroyed)

    def test_close_with_tray_hides(self):
        app = self.make_app(tray_enabled=True)
        self.assertTrue(app.tray.running)
        app.close()
        self.assertFalse(self.destroyed)
        self.assertEqual(app.state(), "withdrawn")

    def test_tray_click_toggles_window(self):
        app = self.make_app(tray_enabled=True)
        app.close()
        self.trays[0].callbacks["on_toggle"]()  # clique no ícone
        app.update()
        self.assertEqual(app.state(), "normal")
        self.trays[0].callbacks["on_toggle"]()
        self.assertEqual(app.state(), "withdrawn")

    def test_tray_quit_really_quits(self):
        app = self.make_app(tray_enabled=True)
        self.trays[0].callbacks["on_quit"]()
        self.assertTrue(self.destroyed)
        self.assertFalse(self.trays[0].running)

    def test_callbacks_from_tray_thread_run_on_tk_thread(self):
        app = self.make_app(tray_enabled=True)
        post = self.trays[0].callbacks["post"]
        thread = threading.Thread(target=lambda: post(app.hide_window))
        thread.start(); thread.join()
        deadline = time.time() + 2
        while app.state() != "withdrawn" and time.time() < deadline:
            app.update(); time.sleep(0.02)
        self.assertEqual(app.state(), "withdrawn")

    def test_start_hidden(self):
        app = self.make_app(tray_enabled=True, start_hidden=True)
        self.assertEqual(app.state(), "withdrawn")

    def test_start_hidden_ignored_without_tray(self):
        app = self.make_app(available=False, tray_enabled=True, start_hidden=True)
        self.assertEqual(app.state(), "normal")  # nunca esconder sem ícone para reabrir
        app.close()
        self.assertTrue(self.destroyed)

    def test_enabling_tray_in_settings_starts_icon(self):
        from dataclasses import replace
        app = self.make_app()
        self.assertFalse(app.tray.running)
        app._on_settings_saved(replace(app.settings, tray_enabled=True))
        self.assertTrue(app.tray.running)
        app._on_settings_saved(replace(app.settings, tray_enabled=False))
        self.assertFalse(app.tray.running)

    def test_saving_settings_does_not_reapply_scaling(self):
        """Regressão: reaplicar a escala movia a janela para outro monitor."""
        import customtkinter as ctk
        app = self.make_app()
        with mock.patch.object(ctk, "set_widget_scaling") as scaling:
            app._on_settings_saved(app.settings)
            scaling.assert_not_called()

    def test_hidden_window_is_not_polled(self):
        app = self.make_app(tray_enabled=True)
        app.hide_window()
        with mock.patch.object(app, "refresh_controls") as refresh:
            app._poll()
            refresh.assert_not_called()


@unittest.skipUnless(HAS_DISPLAY, "requer servidor gráfico")
class SelectTest(unittest.TestCase):
    def setUp(self):
        import customtkinter as ctk
        from src.gui.select import Select
        self.root = ctk.CTk()
        self.addCleanup(self.root.destroy)
        self.chosen = []
        self.select = Select(self.root, values=[f"Item {i}" for i in range(12)], command=self.chosen.append)
        self.select.set("Item 2")
        self.select.pack()
        self.root.update()

    def test_popup_lists_all_items_with_comfortable_height(self):
        from src.gui.select import ITEM_HEIGHT
        self.select._clicked()
        popup = self.select.popup
        self.root.update()
        self.assertEqual(len(popup.buttons), 12)
        self.assertGreaterEqual(popup.buttons[0].winfo_height(), ITEM_HEIGHT)
        self.assertGreaterEqual(popup.winfo_width(), self.select.winfo_width())
        popup.close()

    def test_choose_calls_command_and_closes(self):
        self.select._clicked()
        self.select.popup.buttons[5].invoke()
        self.assertEqual(self.chosen, ["Item 5"])
        self.assertEqual(self.select.get(), "Item 5")
        self.assertIsNone(self.select.popup)

    def test_keyboard_navigation(self):
        self.select._clicked()
        popup = self.select.popup
        self.assertEqual(popup._highlight, 2)  # começa no item selecionado
        popup._move(+1)
        popup._move(+1)
        popup._move(-1)
        popup.choose(popup._values[popup._highlight])
        self.assertEqual(self.chosen[-1], "Item 3")

    def test_escape_and_second_click_close(self):
        self.select._clicked()
        self.select.popup.close()
        self.assertIsNone(self.select.popup)
        self.select._clicked()
        self.select._clicked()
        self.assertIsNone(self.select.popup)


if __name__ == "__main__":
    unittest.main()
