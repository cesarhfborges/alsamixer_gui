import json
import os
import tempfile
import unittest
from dataclasses import replace

from src.core.autostart import AutostartManager, build_desktop_entry
from src.core.interfaces import MixerError
from src.core.mixer_state import (InMemoryMixerStateRepository, JsonMixerStateRepository, MixerStateStore,
                                  SwitchState)
from src.core.models import Direction, SoundCard
from src.core.settings import AppSettings, InMemorySettingsRepository
from src.core.state_keeper import StateKeeper
from tests.test_gui import HAS_DISPLAY, FakeController

SPDIF = SwitchState("PCH", "IEC958,0", Direction.PLAYBACK, True)


class MutableFakeController(FakeController):
    """FakeController cujo hardware muda ao aplicar um switch (como o real)."""

    def __init__(self):
        super().__init__()
        self.cards = [SoundCard(0, "SoloCast", "HyperX SoloCast"), SoundCard(2, "PCH", "HDA Intel PCH")]

    def list_cards(self):
        return list(self.cards)

    def set_switch(self, card, control, direction, enabled):
        super().set_switch(card, control, direction, enabled)
        controls = self.usb if card == 0 else self.hda
        target = next(c for c in controls if c.key == control.key)
        setattr(target, f"{direction.value}_switch", enabled)

    def hardware(self, key):
        return next(c for c in self.hda if c.key == key)


class MixerStateRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, "mixer-state.json")

    def test_round_trip(self):
        repo = JsonMixerStateRepository(self.path)
        repo.save([SPDIF, SwitchState("SoloCast", "Mic,0", Direction.CAPTURE, False)])
        self.assertEqual(repo.load(), [SPDIF, SwitchState("SoloCast", "Mic,0", Direction.CAPTURE, False)])
        with open(self.path) as fh:
            data = json.load(fh)
        self.assertEqual(data["switches"][0],
                         {"card": "PCH", "control": "IEC958,0", "direction": "playback", "enabled": True})

    def test_missing_or_corrupted_file(self):
        repo = JsonMixerStateRepository(self.path)
        self.assertEqual(repo.load(), [])
        with open(self.path, "w") as fh:
            fh.write("{oops")
        self.assertEqual(repo.load(), [])

    def test_invalid_entries_are_ignored(self):
        with open(self.path, "w") as fh:
            json.dump({"switches": [SPDIF.to_dict(), {"card": "X"}, {"card": 1, "control": "a", "direction":
                                                                       "playback", "enabled": True},
                                    {"card": "X", "control": "a", "direction": "lateral", "enabled": True}, 3]},
                      fh)
        self.assertEqual(JsonMixerStateRepository(self.path).load(), [SPDIF])


class MixerStateStoreTest(unittest.TestCase):
    def test_remember_saves_only_on_change(self):
        repo = InMemoryMixerStateRepository()
        store = MixerStateStore(repo)
        store.remember("PCH", "IEC958,0", Direction.PLAYBACK, True)
        store.remember("PCH", "IEC958,0", Direction.PLAYBACK, True)
        self.assertEqual(repo.saves, 1)
        store.remember("PCH", "IEC958,0", Direction.PLAYBACK, False)
        self.assertEqual(repo.states, [replace(SPDIF, enabled=False)])
        self.assertEqual(len(store), 1)

    def test_clear(self):
        store = MixerStateStore(InMemoryMixerStateRepository([SPDIF]))
        store.clear()
        self.assertEqual(len(store), 0)
        self.assertIsNone(store.get("PCH", "IEC958,0", Direction.PLAYBACK))


class StateKeeperTest(unittest.TestCase):
    def setUp(self):
        self.controller = MutableFakeController()
        self.store = MixerStateStore(InMemoryMixerStateRepository([SPDIF]))
        self.keeper = StateKeeper(self.controller, self.store)

    def test_reapplies_when_system_changed_it(self):
        self.assertFalse(self.controller.hardware("IEC958,0").playback_switch)  # S/PDIF desligado (fixture)
        result = self.keeper.enforce()
        self.assertEqual(result.corrected, [SPDIF])
        self.assertTrue(self.controller.hardware("IEC958,0").playback_switch)
        self.assertEqual(self.keeper.enforce().corrected, [])  # já está correto: não reaplica

    def test_uses_card_id_even_if_index_changes(self):
        self.controller.cards = [SoundCard(2, "PCH", "HDA Intel PCH")]  # índice 2 é o que o fake usa p/ HDA
        self.keeper.enforce()
        self.assertEqual(self.controller.calls[-1][1], 2)

    def test_absent_card_and_missing_control_are_skipped(self):
        self.store.remember("USBAntiga", "PCM,0", Direction.PLAYBACK, True)
        self.store.remember("PCH", "NaoExiste,0", Direction.PLAYBACK, True)
        result = self.keeper.enforce()
        self.assertEqual(result.corrected, [SPDIF])
        self.assertEqual(result.errors, [])

    def test_errors_are_reported(self):
        self.controller.fail = True
        result = self.keeper.enforce()
        self.assertEqual(result.corrected, [])
        self.assertIn("falha simulada", result.errors[0])

    def test_empty_store_does_not_touch_hardware(self):
        keeper = StateKeeper(self.controller, MixerStateStore(InMemoryMixerStateRepository()))
        self.assertFalse(keeper.enforce().changed)
        self.assertEqual(self.controller.calls, [])


class AutostartTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, "autostart", "alsamixer-gui.desktop")

    def test_desktop_entry(self):
        entry = build_desktop_entry(["/opt/my app/.venv/bin/python", "/opt/my app/main.py", "--autostart"])
        self.assertIn('Exec="/opt/my app/.venv/bin/python" "/opt/my app/main.py" --autostart', entry)
        self.assertIn("X-GNOME-Autostart-Delay=", entry)
        self.assertTrue(entry.startswith("[Desktop Entry]\nType=Application"))

    def test_default_command_uses_venv_python_and_project_main(self):
        import sys
        manager = AutostartManager(self.path)
        self.assertEqual(manager.command[0], sys.executable)
        self.assertTrue(manager.command[1].endswith("main.py") and os.path.isabs(manager.command[1]))
        self.assertTrue(os.path.exists(manager.command[1]))
        self.assertEqual(manager.command[2], "--autostart")

    def test_sync_enable_disable_and_rewrite_when_project_moves(self):
        manager = AutostartManager(self.path, ["/a/python", "/a/main.py", "--autostart"])
        manager.sync(True)
        self.assertTrue(manager.is_enabled() and manager.is_current())
        moved = AutostartManager(self.path, ["/b/python", "/b/main.py", "--autostart"])
        self.assertFalse(moved.is_current())
        moved.sync(True)
        with open(self.path) as fh:
            self.assertIn("/b/main.py", fh.read())
        moved.sync(False)
        self.assertFalse(os.path.exists(self.path))
        moved.sync(False)  # idempotente


class CommandLineTest(unittest.TestCase):
    def test_flags(self):
        from src.main import parse_args
        self.assertTrue(parse_args(["--autostart"]).autostart)
        self.assertTrue(parse_args(["--apply-state"]).apply_state)
        self.assertFalse(parse_args([]).autostart)


class FakeTray:
    def __init__(self, **callbacks):
        self.available, self.running, self.callbacks = True, False, callbacks

    def start(self):
        self.running = True

    def stop(self):
        self.running = False


@unittest.skipUnless(HAS_DISPLAY, "requer servidor gráfico")
class WindowStateIntegrationTest(unittest.TestCase):
    def make_app(self, states=(), autostart=None, start_in_tray=False, **settings):
        from src.gui.main_window import AlsamixerGUI
        from src.core.layout import Section
        self.Section = Section
        self.controller = MutableFakeController()
        self.store = MixerStateStore(InMemoryMixerStateRepository(list(states)))
        self.settings_repo = InMemorySettingsRepository(
            AppSettings(poll_interval_ms=0, theme="Dark", default_card="PCH", **settings))
        app = AlsamixerGUI(self.controller, settings_repository=self.settings_repo,
                           tray_factory=lambda **kw: FakeTray(**kw), mixer_state_store=self.store,
                           autostart=autostart, start_in_tray=start_in_tray)
        self.addCleanup(app.destroy)
        return app

    def spdif_view(self, app):
        return app.panels[self.Section.OUTPUT].views[("IEC958,0", "volume", "playback")]

    def test_toggling_mute_in_app_is_remembered(self):
        app = self.make_app()
        view = self.spdif_view(app)
        self.assertEqual(view.saved_label.cget("text"), "")
        view.mute_checkbox.toggle()  # desmarca "Mudo" => liga o S/PDIF
        self.assertEqual(self.store.states(), [SPDIF])
        self.assertEqual(view.saved_label.cget("text"), "● salvo")

    def test_saved_state_is_restored_on_start(self):
        app = self.make_app(states=[SPDIF])
        self.assertTrue(self.controller.hardware("IEC958,0").playback_switch)
        self.assertIn("S/PDIF (PCH)", app.status_label.cget("text"))
        self.assertEqual(self.spdif_view(app).state_label.cget("text"), "ON")

    def test_restore_disabled(self):
        app = self.make_app(states=[SPDIF], restore_state=False, keep_state=False)
        self.assertFalse(self.controller.hardware("IEC958,0").playback_switch)
        self.assertIsNone(app._keeper_job)

    def test_keeper_reapplies_after_system_change_even_when_hidden(self):
        app = self.make_app(states=[SPDIF], tray_enabled=True)
        app.hide_window()
        self.controller.hardware("IEC958,0").playback_switch = False  # ex.: WirePlumber após o login
        app._keeper_tick()
        self.assertTrue(self.controller.hardware("IEC958,0").playback_switch)
        self.assertIsNotNone(app._keeper_job)

    def test_without_keep_state_stops_after_startup_window(self):
        app = self.make_app(states=[SPDIF], keep_state=False)
        app._keeper_deadline = 0
        self.controller.hardware("IEC958,0").playback_switch = False
        app._keeper_tick()
        self.assertFalse(self.controller.hardware("IEC958,0").playback_switch)
        self.assertIsNone(app._keeper_job)

    def test_clear_saved_states(self):
        app = self.make_app(states=[SPDIF])
        app.clear_saved_states()
        self.assertEqual(len(self.store), 0)
        self.assertEqual(self.spdif_view(app).saved_label.cget("text"), "")

    def test_autostart_setting_writes_file_and_enables_tray(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        manager = AutostartManager(os.path.join(tmp.name, "a.desktop"), ["/x/python", "/x/main.py", "--autostart"])
        app = self.make_app(autostart=manager)
        self.assertFalse(manager.is_enabled())
        app._on_settings_saved(replace(app.settings, autostart=True))
        self.assertTrue(manager.is_current())
        self.assertTrue(app.settings.tray_enabled and app.tray.running)
        self.assertTrue(self.settings_repo.settings.autostart)
        app._on_settings_saved(replace(app.settings, autostart=False))
        self.assertFalse(manager.is_enabled())

    def test_started_by_autostart_goes_to_tray(self):
        app = self.make_app(start_in_tray=True, tray_enabled=True)
        self.assertEqual(app.state(), "withdrawn")

    def test_settings_dialog_shows_saved_states(self):
        app = self.make_app(states=[SPDIF])
        app.open_settings()
        dialog = app.settings_dialog
        self.assertEqual(str(dialog.clear_states_button.cget("state")), "normal")
        dialog.clear_states_button.invoke()
        self.assertEqual(len(self.store), 0)
        self.assertEqual(str(dialog.clear_states_button.cget("state")), "disabled")
        dialog.destroy()


if __name__ == "__main__":
    unittest.main()
