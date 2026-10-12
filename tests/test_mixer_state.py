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
        entry = build_desktop_entry(["/opt/my app/.venv/bin/python", "/opt/my app/main.py", "--minimized"])
        self.assertIn('Exec="/opt/my app/.venv/bin/python" "/opt/my app/main.py" --minimized', entry)
        self.assertIn("X-GNOME-Autostart-Delay=", entry)
        self.assertTrue(entry.startswith("[Desktop Entry]\nType=Application"))

    def test_default_command_uses_venv_python_and_project_main(self):
        import sys
        manager = AutostartManager(self.path)
        self.assertEqual(manager.command[0], sys.executable)
        self.assertTrue(manager.command[1].endswith("main.py") and os.path.isabs(manager.command[1]))
        self.assertTrue(os.path.exists(manager.command[1]))
        self.assertEqual(manager.command[2], "--minimized")

    def test_sync_enable_disable_and_rewrite_when_project_moves(self):
        manager = AutostartManager(self.path, ["/a/python", "/a/main.py", "--minimized"])
        manager.sync(True)
        self.assertTrue(manager.is_enabled() and manager.is_current())
        moved = AutostartManager(self.path, ["/b/python", "/b/main.py", "--minimized"])
        self.assertFalse(moved.is_current())
        moved.sync(True)
        with open(self.path) as fh:
            self.assertIn("/b/main.py", fh.read())
        moved.sync(False)
        self.assertFalse(os.path.exists(self.path))
        moved.sync(False)  # idempotente

    def test_respects_disable_from_mint_startup_applications(self):
        manager = AutostartManager(self.path, ["/a/python", "/a/main.py", "--minimized"])
        manager.enable()
        with open(self.path, "a") as fh:
            fh.write("X-GNOME-Autostart-enabled=false\n")
        manager.sync(True)  # não regrava a escolha do usuário
        self.assertTrue(manager.disabled_by_user())
        self.assertIn("TryExec=/a/python", manager.expected_content)


class CommandLineTest(unittest.TestCase):
    def test_flags(self):
        from src.main import parse_args
        self.assertTrue(parse_args(["--minimized"]).minimized)
        self.assertTrue(parse_args(["--apply-state"]).apply_state)
        self.assertFalse(parse_args([]).minimized)


if __name__ == "__main__":
    unittest.main()
