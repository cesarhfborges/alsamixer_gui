import os
import unittest

from src.core.amixer_parser import parse_cards, parse_scontents
from src.core.interfaces import MixerError
from src.core.layout import ControlKind, Section, build_layout
from src.core.linux_mixer import AlsaMixerController
from src.core.models import Direction

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def fixture(name: str) -> str:
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return fh.read()


class ParseCardsTest(unittest.TestCase):
    def test_parses_real_proc_cards(self):
        cards = parse_cards(fixture("proc_asound_cards.txt"))
        self.assertEqual([c.index for c in cards], [0, 1, 2, 3])
        self.assertEqual(cards[0].id, "SoloCast")
        self.assertEqual(cards[2].name, "HDA Intel PCH")
        self.assertEqual(cards[2].label, "2: HDA Intel PCH")

    def test_empty_input(self):
        self.assertEqual(parse_cards("--- no soundcards ---"), [])


class ParseScontentsTest(unittest.TestCase):
    def setUp(self):
        self.controls = {c.key: c for c in parse_scontents(fixture("card_hda_intel.txt"))}

    def test_playback_volume_and_switch(self):
        master = self.controls["Master,0"]
        self.assertEqual(master.playback_volume, 97)
        self.assertTrue(master.playback_switch)
        self.assertIsNone(master.capture_volume)

    def test_muted_control(self):
        headphone = self.controls["Headphone,0"]
        self.assertEqual(headphone.playback_volume, 0)
        self.assertTrue(headphone.is_muted(Direction.PLAYBACK))

    def test_volume_without_switch(self):
        pcm = self.controls["PCM,0"]
        self.assertEqual(pcm.playback_volume, 98)
        self.assertFalse(pcm.has_switch(Direction.PLAYBACK))

    def test_capture_controls_with_index(self):
        self.assertEqual(self.controls["Capture,0"].capture_volume, 100)
        self.assertTrue(self.controls["Capture,0"].capture_switch)
        self.assertFalse(self.controls["Capture,1"].capture_switch)
        self.assertEqual(self.controls["Capture,1"].display_name, "Capture 1")

    def test_generic_boost_goes_to_capture(self):
        boost = self.controls["Rear Mic Boost,0"]
        self.assertEqual(boost.capture_volume, 100)
        self.assertIsNone(boost.playback_volume)

    def test_enum(self):
        source = self.controls["Input Source,0"]
        self.assertEqual(source.enum_items, ["Rear Mic", "Front Mic", "Line"])
        self.assertEqual(source.enum_value, "Rear Mic")
        self.assertTrue(source.is_enum)

    def test_switch_only(self):
        iec = self.controls["IEC958,0"]
        self.assertFalse(iec.playback_switch)
        self.assertIsNone(iec.playback_volume)

    def test_iec958_is_displayed_as_spdif(self):
        self.assertEqual(self.controls["IEC958,0"].display_name, "S/PDIF")
        self.assertEqual(self.controls["IEC958 Default PCM,0"].display_name, "S/PDIF Default PCM")
        self.assertEqual(self.controls["IEC958,0"].key, "IEC958,0")  # amixer continua recebendo o nome real

    def test_combined_playback_and_capture_line(self):
        text = (
            "Simple mixer control 'Line',0\n"
            "  Capabilities: pvolume pswitch cvolume cswitch\n"
            "  Front Left: Playback 10 [40%] [-5.00dB] [on] Capture 3 [20%] [off]\n"
            "  Front Right: Playback 20 [60%] [-3.00dB] [off] Capture 3 [30%] [off]\n"
        )
        line = parse_scontents(text)[0]
        self.assertEqual(line.playback_volume, 50)
        self.assertEqual(line.capture_volume, 25)
        self.assertTrue(line.playback_switch)  # pelo menos um canal ligado
        self.assertFalse(line.capture_switch)


class LayoutTest(unittest.TestCase):
    def test_sections_for_hda(self):
        layout = build_layout(parse_scontents(fixture("card_hda_intel.txt")))
        output = [s.control.key for s in layout[Section.OUTPUT]]
        inputs = [s.control.key for s in layout[Section.INPUT]]
        options = {s.control.key: s.kind for s in layout[Section.OPTIONS]}

        self.assertIn("Master,0", output)
        self.assertNotIn("Capture,0", output)
        self.assertIn("Capture,0", inputs)
        self.assertIn("Rear Mic Boost,0", inputs)
        self.assertIn("IEC958,0", output)  # S/PDIF fica junto das saídas, como no alsamixer
        self.assertIn("IEC958 Default PCM,0", output)
        self.assertEqual(options["Auto-Mute Mode,0"], ControlKind.ENUM)
        self.assertTrue(all(kind is ControlKind.ENUM for kind in options.values()))
        self.assertTrue(all(s.kind is ControlKind.VOLUME for s in layout[Section.OUTPUT] + layout[Section.INPUT]))

    def test_usb_mic_sections(self):
        layout = build_layout(parse_scontents(fixture("card_usb_mic.txt")))
        self.assertEqual([s.control.key for s in layout[Section.OUTPUT]], ["Extension Unit,0"])
        self.assertEqual([s.control.key for s in layout[Section.INPUT]], ["Mic,0"])
        self.assertEqual(layout[Section.OPTIONS], [])

    def test_control_with_both_directions_appears_in_both_tabs(self):
        control = parse_scontents(
            "Simple mixer control 'Line',0\n"
            "  Capabilities: pvolume pswitch cvolume cswitch\n"
            "  Mono: Playback 1 [10%] [on] Capture 1 [10%] [on]\n"
        )
        layout = build_layout(control)
        self.assertEqual(layout[Section.OUTPUT][0].direction, Direction.PLAYBACK)
        self.assertEqual(layout[Section.INPUT][0].direction, Direction.CAPTURE)


class FakeRunner:
    def __init__(self, output: str = ""):
        self.output = output
        self.calls = []

    def __call__(self, args):
        self.calls.append(list(args))
        return self.output


class AlsaMixerControllerTest(unittest.TestCase):
    def setUp(self):
        self.runner = FakeRunner(fixture("card_hda_intel.txt"))
        self.mixer = AlsaMixerController(runner=self.runner)
        self.controls = {c.key: c for c in self.mixer.get_controls(2)}

    def test_get_controls_uses_mapped_scale(self):
        self.assertEqual(self.runner.calls[0], ["amixer", "-c", "2", "-M", "scontents"])

    def test_set_volume_playback(self):
        self.mixer.set_volume(2, self.controls["Master,0"], Direction.PLAYBACK, 55)
        self.assertEqual(self.runner.calls[-1],
                         ["amixer", "-q", "-c", "2", "-M", "sset", "Master,0", "playback", "55%"])

    def test_set_volume_is_clamped(self):
        self.mixer.set_volume(2, self.controls["Master,0"], Direction.PLAYBACK, 150)
        self.assertEqual(self.runner.calls[-1][-1], "100%")

    def test_set_volume_generic_has_no_direction(self):
        self.mixer.set_volume(2, self.controls["Rear Mic Boost,0"], Direction.CAPTURE, 30)
        self.assertEqual(self.runner.calls[-1][-2:], ["Rear Mic Boost,0", "30%"])

    def test_mute_and_unmute(self):
        self.mixer.set_switch(2, self.controls["Master,0"], Direction.PLAYBACK, False)
        self.assertEqual(self.runner.calls[-1][-2:], ["playback", "mute"])
        self.mixer.set_switch(2, self.controls["Capture,0"], Direction.CAPTURE, False)
        self.assertEqual(self.runner.calls[-1][-2:], ["capture", "nocap"])
        self.mixer.set_switch(2, self.controls["Capture,0"], Direction.CAPTURE, True)
        self.assertEqual(self.runner.calls[-1][-2:], ["capture", "cap"])

    def test_set_enum(self):
        self.mixer.set_enum(2, self.controls["Input Source,1"], "Line")
        self.assertEqual(self.runner.calls[-1][-2:], ["Input Source,1", "Line"])

    def test_set_enum_rejects_unknown_value(self):
        with self.assertRaises(MixerError):
            self.mixer.set_enum(2, self.controls["Input Source,1"], "Inexistente")

    def test_list_cards_missing_file(self):
        with self.assertRaises(MixerError):
            AlsaMixerController(cards_path="/caminho/inexistente").list_cards()


class ThemeDetectionTest(unittest.TestCase):
    def setUp(self):
        from src.gui.theme_manager import ThemeManager
        self.decide = ThemeManager.mode_from_settings

    def test_color_scheme_wins(self):
        self.assertEqual(self.decide(["prefer-dark"], ["Mint-L"]), "Dark")
        self.assertEqual(self.decide(["prefer-light"], ["Mint-L-Dark"]), "Light")

    def test_mint_dark_theme_with_default_scheme(self):
        # Caso real: color-scheme 'default' e tema GTK Mint-L-Dark-Blue
        self.assertEqual(self.decide(["default", None], [None, "Mint-L-Dark-Blue"]), "Dark")
        self.assertEqual(self.decide(["default"], ["Mint-Y"]), "Light")

    def test_inconclusive(self):
        self.assertIsNone(self.decide([None, "default"], [None, None]))


if __name__ == "__main__":
    unittest.main()
