import json
import os
import tempfile
import unittest

from src.core.models import SoundCard
from src.core.settings import AppSettings, JsonSettingsRepository, LAST_USED

CARDS = [SoundCard(0, "SoloCast", "HyperX SoloCast"), SoundCard(2, "PCH", "HDA Intel PCH")]


class AppSettingsTest(unittest.TestCase):
    def test_initial_card_priority(self):
        self.assertEqual(AppSettings(default_card="PCH", last_card="SoloCast").initial_card(CARDS).id, "PCH")
        self.assertEqual(AppSettings(default_card=LAST_USED, last_card="PCH").initial_card(CARDS).id, "PCH")
        self.assertEqual(AppSettings(default_card="Sumiu", last_card="Sumiu2").initial_card(CARDS).id, "SoloCast")
        self.assertIsNone(AppSettings().initial_card([]))

    def test_initial_tab(self):
        self.assertEqual(AppSettings().initial_tab(), "Saída")
        self.assertEqual(AppSettings(last_tab="Opções").initial_tab(), "Opções")
        self.assertEqual(AppSettings(default_tab="Entrada", last_tab="Opções").initial_tab(), "Entrada")

    def test_invalid_values_fall_back_to_defaults(self):
        settings = AppSettings.from_dict({"settings": {
            "theme": "Roxo", "ui_scale": 7, "wheel_step": "x", "poll_interval_ms": 3,
            "default_tab": "Nada", "remember_window": "sim", "last_tab": 5, "desconhecido": 1,
            "default_card": "PCH",
        }})
        self.assertEqual(settings, AppSettings(default_card="PCH"))


class JsonSettingsRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, "sub", "settings.json")
        self.repo = JsonSettingsRepository(self.path)

    def test_missing_file_returns_defaults(self):
        self.assertEqual(self.repo.load(), AppSettings())

    def test_round_trip(self):
        settings = AppSettings(theme="Light", ui_scale=1.25, default_card="PCH", last_tab="Entrada",
                               window_geometry="900x600+10+20", remember_window=False)
        self.repo.save(settings)
        self.assertEqual(self.repo.load(), settings)
        with open(self.path, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data["version"], 1)
        self.assertEqual(data["settings"]["default_card"], "PCH")

    def test_corrupted_file_returns_defaults(self):
        os.makedirs(os.path.dirname(self.path))
        with open(self.path, "w") as fh:
            fh.write("{ isto não é json")
        self.assertEqual(self.repo.load(), AppSettings())

    def test_save_leaves_no_temp_files(self):
        self.repo.save(AppSettings())
        self.assertEqual(os.listdir(os.path.dirname(self.path)), ["settings.json"])

    def test_xdg_config_home(self):
        from src.core.settings import default_settings_path
        old = os.environ.get("XDG_CONFIG_HOME")
        os.environ["XDG_CONFIG_HOME"] = "/tmp/xdg"
        try:
            self.assertEqual(default_settings_path(), "/tmp/xdg/alsamixer-gui/settings.json")
        finally:
            if old is None:
                del os.environ["XDG_CONFIG_HOME"]
            else:
                os.environ["XDG_CONFIG_HOME"] = old


if __name__ == "__main__":
    unittest.main()
