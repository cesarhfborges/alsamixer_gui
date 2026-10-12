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


class FakeTray:
    def __init__(self, **callbacks):
        self.available, self.running, self.callbacks = True, False, callbacks

    def start(self):
        self.running = True

    def stop(self):
        self.running = False


@unittest.skipUnless(HAS_DISPLAY, "requer servidor gráfico")
class GuiSmokeTest(unittest.TestCase):
    """Um teste de fumaça da janela: monta, interage e encerra (o resto é testado sem GUI)."""

    def test_main_flow(self):
        from src.core.mixer_state import InMemoryMixerStateRepository, MixerStateStore
        from src.gui.main_window import AlsamixerGUI
        controller = FakeController()
        store = MixerStateStore(InMemoryMixerStateRepository())
        repo = InMemorySettingsRepository(AppSettings(poll_interval_ms=0, theme="Dark", default_card="PCH",
                                                      tray_enabled=True))
        app = AlsamixerGUI(controller, settings_repository=repo, mixer_state_store=store,
                           tray_factory=lambda **kw: FakeTray(**kw))

        # placa padrão + abas montadas
        self.assertEqual(app.current_card.id, "PCH")
        output = app.panels[Section.OUTPUT].views
        self.assertIn(("Master,0", "volume", "playback"), output)
        self.assertIn(("Auto-Mute Mode,0", "enum", ""), app.panels[Section.OPTIONS].views)

        # mudo no S/PDIF: aplica no mixer e é lembrado para restaurar no próximo login
        spdif = output[("IEC958,0", "volume", "playback")]
        spdif.mute_checkbox.toggle()
        self.assertEqual(controller.calls[-1], ("switch", 2, "IEC958,0", Direction.PLAYBACK, True))
        self.assertEqual(len(store), 1)

        # fechar com bandeja ativa só esconde; o menu da bandeja tem "Encerrar"
        app.close()
        self.assertEqual(app.state(), "withdrawn")
        app.tray.callbacks["on_menu"](100, 100)
        self.assertEqual(app.tray_menu.buttons[-1].cget("text"), "Encerrar")
        app.tray_menu.close()

        # botão Encerrar da janela encerra de verdade
        app.quit_button.invoke()
        self.assertFalse(app.tray.running)


if __name__ == "__main__":
    unittest.main()
