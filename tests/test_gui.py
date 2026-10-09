import copy
import os
import unittest

from src.core.amixer_parser import parse_scontents
from src.core.interfaces import AudioController, MixerError
from src.core.layout import ControlKind, ControlSpec, Section
from src.core.models import Direction, SoundCard
from src.core.settings import AppSettings, InMemorySettingsRepository

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")

try:
    import tkinter
    tkinter.Tk().destroy()
    HAS_DISPLAY = True
except Exception:  # sem servidor gráfico
    HAS_DISPLAY = False


class FakeController(AudioController):
    def __init__(self):
        with open(os.path.join(FIXTURES, "card_hda_intel.txt"), encoding="utf-8") as fh:
            self.hda = parse_scontents(fh.read())
        with open(os.path.join(FIXTURES, "card_usb_mic.txt"), encoding="utf-8") as fh:
            self.usb = parse_scontents(fh.read())
        self.calls = []
        self.fail = False

    def list_cards(self):
        return [SoundCard(0, "SoloCast", "HyperX SoloCast"), SoundCard(2, "PCH", "HDA Intel PCH")]

    def get_controls(self, card):
        return copy.deepcopy(self.usb if card == 0 else self.hda)

    def _record(self, *call):
        if self.fail:
            raise MixerError("falha simulada")
        self.calls.append(call)

    def set_volume(self, card, control, direction, percent):
        self._record("volume", card, control.key, direction, percent)

    def set_switch(self, card, control, direction, enabled):
        self._record("switch", card, control.key, direction, enabled)

    def set_enum(self, card, control, value):
        self._record("enum", card, control.key, value)


@unittest.skipUnless(HAS_DISPLAY, "requer servidor gráfico")
class MainWindowTest(unittest.TestCase):
    def setUp(self):
        from src.gui.main_window import AlsamixerGUI
        self.controller = FakeController()
        self.repo = InMemorySettingsRepository(AppSettings(poll_interval_ms=0, theme="Dark"))
        self.app = AlsamixerGUI(self.controller, settings_repository=self.repo)
        self.app.update_idletasks()

    def tearDown(self):
        self.app.destroy()

    def views_of(self, section):
        return self.app.panels[section].views

    def test_first_card_selected_and_tabs_populated(self):
        self.assertEqual(self.app.card_select.get(), "0: HyperX SoloCast")
        self.assertEqual(list(self.views_of(Section.OUTPUT)), [("Extension Unit,0", "volume", "playback")])
        self.assertEqual(len(self.views_of(Section.INPUT)), 1)

    def test_switching_card_rebuilds_tabs(self):
        self.app._on_card_selected("2: HDA Intel PCH")
        output = self.views_of(Section.OUTPUT)
        self.assertIn(("Master,0", "volume", "playback"), output)
        self.assertIn(("Capture,0", "volume", "capture"), self.views_of(Section.INPUT))
        self.assertIn(("Auto-Mute Mode,0", "enum", ""), self.views_of(Section.OPTIONS))

    def test_all_views_share_the_same_contract(self):
        from src.gui.control_widgets import ControlView
        self.app._on_card_selected("2: HDA Intel PCH")
        for section in Section:
            for view in self.views_of(section).values():
                self.assertIsInstance(view, ControlView)
                self.assertIs(view.actions, self.app.actions)

    def test_slider_sends_volume(self):
        self.app._on_card_selected("2: HDA Intel PCH")
        view = self.views_of(Section.OUTPUT)[("Master,0", "volume", "playback")]
        view.slider.set(42)
        view._on_slider_move(42)
        self.assertEqual(view.value_label.cget("text"), "42%")
        view._flush_volume()
        self.assertEqual(self.controller.calls[-1], ("volume", 2, "Master,0", Direction.PLAYBACK, 42))

    def test_mute_checkbox(self):
        self.app._on_card_selected("2: HDA Intel PCH")
        view = self.views_of(Section.OUTPUT)[("Master,0", "volume", "playback")]
        self.assertFalse(view.mute_checkbox.get())
        view.mute_checkbox.toggle()
        self.assertEqual(self.controller.calls[-1], ("switch", 2, "Master,0", Direction.PLAYBACK, False))

    def test_volume_only_control_has_no_mute(self):
        self.app._on_card_selected("2: HDA Intel PCH")
        pcm = self.views_of(Section.OUTPUT)[("PCM,0", "volume", "playback")]
        self.assertIsNone(pcm.mute_checkbox)
        self.assertIsNotNone(pcm.slider)

    def test_sliders_are_vertical(self):
        self.app._on_card_selected("2: HDA Intel PCH")
        view = self.views_of(Section.OUTPUT)[("Master,0", "volume", "playback")]
        self.assertEqual(view.slider.cget("orientation"), "vertical")
        self.assertEqual(self.app.panels[Section.OUTPUT]._orientation, "horizontal")

    def test_mouse_wheel_on_slider_changes_volume(self):
        self.app._on_card_selected("2: HDA Intel PCH")
        view = self.views_of(Section.OUTPUT)[("Front Mic,0", "volume", "playback")]
        self.assertEqual(view._on_wheel(+3), "break")
        self.assertEqual(view.value_label.cget("text"), "3%")
        view._flush_volume()
        self.assertEqual(self.controller.calls[-1], ("volume", 2, "Front Mic,0", Direction.PLAYBACK, 3))

    def test_mouse_wheel_scrolls_panel_horizontally(self):
        self.app._on_card_selected("2: HDA Intel PCH")
        self.app.update()
        panel = self.app.panels[Section.OUTPUT]
        canvas = panel._parent_canvas
        start = canvas.xview()[0]
        name_label = self.views_of(Section.OUTPUT)[("Master,0", "volume", "playback")].name_label
        panel._mouse_wheel_all(type("E", (), {"widget": name_label, "num": 5, "delta": 0})())
        self.assertGreater(canvas.xview()[0], start)

    def test_enum_option(self):
        self.app._on_card_selected("2: HDA Intel PCH")
        options = self.views_of(Section.OPTIONS)
        options[("Input Source,0", "enum", "")]._on_select("Line")
        self.assertEqual(self.controller.calls[-1], ("enum", 2, "Input Source,0", "Line"))

    def test_spdif_in_output_with_mute(self):
        self.app._on_card_selected("2: HDA Intel PCH")
        spdif = self.views_of(Section.OUTPUT)[("IEC958,0", "volume", "playback")]
        self.assertEqual(spdif.name_label.cget("text"), "S/PDIF")
        self.assertIsNone(spdif.slider)
        self.assertEqual(spdif.state_label.cget("text"), "OFF")
        spdif.mute_checkbox.toggle()  # desmarca "Mudo" => liga a saída
        self.assertEqual(self.controller.calls[-1], ("switch", 2, "IEC958,0", Direction.PLAYBACK, True))
        self.assertEqual(spdif.state_label.cget("text"), "ON")

    def test_theme_switch_keeps_explicit_colors(self):
        import customtkinter as ctk
        self.app._on_card_selected("2: HDA Intel PCH")
        view = self.views_of(Section.OUTPUT)[("Master,0", "volume", "playback")]
        self.assertIsInstance(view.cget("fg_color"), tuple)
        self.assertIsInstance(self.app.panels[Section.OUTPUT].cget("fg_color"), tuple)
        ctk.set_appearance_mode("Dark")
        self.app.update_idletasks()
        ctk.set_appearance_mode("Light")

    def test_external_change_updates_view(self):
        self.app._on_card_selected("2: HDA Intel PCH")
        master = next(c for c in self.controller.hda if c.key == "Master,0")
        master.playback_volume = 10
        master.playback_switch = False
        self.app.refresh_controls()
        view = self.views_of(Section.OUTPUT)[("Master,0", "volume", "playback")]
        self.assertEqual(int(view.slider.get()), 10)
        self.assertTrue(view.mute_checkbox.get())

    def test_unchanged_state_is_not_redrawn(self):
        self.app._on_card_selected("2: HDA Intel PCH")
        view = self.views_of(Section.OUTPUT)[("Master,0", "volume", "playback")]
        rendered = []
        view._render = rendered.append
        self.app.refresh_controls()
        self.assertEqual(rendered, [])

    def test_error_is_shown_in_status(self):
        self.app._on_card_selected("2: HDA Intel PCH")
        self.controller.fail = True
        view = self.views_of(Section.OUTPUT)[("Master,0", "volume", "playback")]
        view.mute_checkbox.toggle()
        self.assertIn("falha simulada", self.app.status_label.cget("text"))
        self.assertFalse(view.mute_checkbox.get())  # estado real restaurado

    def test_factory_is_extensible(self):
        from src.gui.control_widgets import ControlViewFactory, EnumControlView
        factory = ControlViewFactory()
        with self.assertRaises(ValueError):
            factory.create(self.app, ControlSpec(self.controller.hda[0], ControlKind.ENUM), self.app.actions)
        factory.register(ControlKind.ENUM, EnumControlView)
        source = next(c for c in self.controller.hda if c.is_enum)
        view = factory.create(self.app, ControlSpec(source, ControlKind.ENUM), self.app.actions)
        self.assertIsInstance(view, EnumControlView)


@unittest.skipUnless(HAS_DISPLAY, "requer servidor gráfico")
class SettingsIntegrationTest(unittest.TestCase):
    def make_app(self, **settings):
        from src.gui.main_window import AlsamixerGUI
        self.repo = InMemorySettingsRepository(AppSettings(poll_interval_ms=0, theme="Dark", **settings))
        self.app = AlsamixerGUI(FakeController(), settings_repository=self.repo)
        self.addCleanup(self.app.destroy)
        return self.app

    def test_default_card_is_selected_on_start(self):
        app = self.make_app(default_card="PCH")
        self.assertEqual(app.current_card.id, "PCH")
        self.assertEqual(app.card_select.get(), "2: HDA Intel PCH")

    def test_last_used_card_and_tab_are_restored(self):
        app = self.make_app(last_card="PCH", last_tab="Entrada")
        self.assertEqual(app.current_card.id, "PCH")
        self.assertEqual(app.tabview.get(), "Entrada")

    def test_missing_default_card_falls_back_to_first(self):
        app = self.make_app(default_card="NaoExiste")
        self.assertEqual(app.current_card.id, "SoloCast")

    def test_card_selection_is_saved_as_state(self):
        app = self.make_app()
        app._on_card_selected("2: HDA Intel PCH")
        self.assertEqual(self.repo.settings.last_card, "PCH")

    def test_close_saves_window_geometry(self):
        from src.gui.main_window import AlsamixerGUI
        repo = InMemorySettingsRepository(AppSettings(poll_interval_ms=0, theme="Dark"))
        app = AlsamixerGUI(FakeController(), settings_repository=repo)
        app.update()
        app.close()
        self.assertRegex(repo.settings.window_geometry, r"^\d+x\d+$")

    def test_settings_dialog_has_a_field_for_every_preference(self):
        from src.gui.settings_dialog import preference_attrs
        app = self.make_app()
        app.open_settings()
        dialog = app.settings_dialog
        self.assertEqual(sorted(dialog._selectors), sorted(preference_attrs()))
        dialog.destroy()

    def test_settings_dialog_saves_and_applies(self):
        app = self.make_app()
        app.open_settings()
        dialog = app.settings_dialog
        selector, mapping = dialog._selectors["default_card"]
        selector.set("HDA Intel PCH")
        dialog._selectors["wheel_step"][0].set("10%")
        dialog._selectors["theme"][0].set("Claro")
        dialog.save()
        self.assertEqual(self.repo.settings.default_card, "PCH")
        self.assertEqual(self.repo.settings.wheel_step, 10)
        self.assertEqual(app.view_factory.options.wheel_step, 10)
        import customtkinter as ctk
        self.assertEqual(ctk.get_appearance_mode(), "Light")
        ctk.set_appearance_mode("Dark")

    def test_settings_dialog_cancel_keeps_settings(self):
        app = self.make_app()
        app.open_settings()
        dialog = app.settings_dialog
        dialog._selectors["wheel_step"][0].set("10%")
        dialog.destroy()
        self.assertEqual(app.settings.wheel_step, 3)

    def test_restore_defaults(self):
        app = self.make_app(wheel_step=10)
        app.open_settings()
        dialog = app.settings_dialog
        dialog.restore_defaults()
        self.assertEqual(dialog.selected_settings().wheel_step, 3)
        self.assertEqual(dialog.selected_settings().poll_interval_ms, 2000)
        dialog.destroy()

    def test_unavailable_default_card_stays_visible(self):
        app = self.make_app(default_card="USBAntiga")
        app.open_settings()
        selector, _ = app.settings_dialog._selectors["default_card"]
        self.assertEqual(selector.get(), "USBAntiga (indisponível)")
        app.settings_dialog.destroy()


if __name__ == "__main__":
    unittest.main()
