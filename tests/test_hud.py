import unittest
from PIL import Image, ImageEnhance, ImageDraw
from aion2_farm.hud import HudMonitor, reference_image, region_crop, decode_reference, icon_is_ready, mana_fraction
from aion2_farm.models import Profile, Skill


def frame(mana=1.0, cooldown=False):
    image = Image.new("RGB", (300, 200), (8, 8, 8))
    draw = ImageDraw.Draw(image)
    if mana:
        draw.rectangle((10, 10, 10 + round(128 * mana) - 1, 17), fill=(20, 160, 220))
    for x in range(32):
        for y in range(32):
            image.putpixel((20 + x, 50 + y), (70 + x * 3, 40 + y * 4, 180))
    if cooldown:
        image.paste(ImageEnhance.Brightness(image.crop((20, 50, 52, 82))).enhance(.35), (20, 50))
    return image


class HudTests(unittest.TestCase):
    def setUp(self):
        ready = frame()
        self.profile = Profile(max_mana=100, vision_size=[300, 200], mana_region=[10, 10, 128, 8],
                               mana_reference=reference_image(region_crop(ready, [10, 10, 128, 8])),
                               skills=[Skill("1", mana_cost=30, ready_region=[20, 50, 32, 32],
                                             ready_reference=reference_image(region_crop(ready, [20, 50, 32, 32])))])
        self.now = 0.0
        self.current = ready
        self.monitor = HudMonitor(self.profile, capture=lambda process: self.current, clock=lambda: self.now)

    def settle(self):
        self.monitor.poll()
        self.now += .16
        self.monitor.poll()

    def test_mana_and_two_stable_ready_frames_are_required(self):
        self.assertFalse(self.monitor.can_use(0, self.profile.skills[0]))
        self.now += .16
        self.assertTrue(self.monitor.can_use(0, self.profile.skills[0]))

    def test_insufficient_mana_blocks_a_ready_skill(self):
        self.current = frame(mana=.2)
        self.settle()
        self.assertFalse(self.monitor.can_use(0, self.profile.skills[0]))

    def test_visible_cooldown_blocks_skill_despite_full_mana(self):
        self.current = frame(cooldown=True)
        self.settle()
        self.assertFalse(self.monitor.can_use(0, self.profile.skills[0]))

    def test_unknown_mana_cost_never_means_free(self):
        self.profile.skills[0].mana_cost = None
        self.settle()
        self.assertFalse(self.monitor.can_use(0, self.profile.skills[0]))

    def test_recent_cast_reserves_mana_and_resets_readiness(self):
        self.profile.skills[0].mana_cost = 60
        self.settle()
        self.assertTrue(self.monitor.can_use(0, self.profile.skills[0]))
        self.monitor.consumed(0, self.profile.skills[0])
        self.assertFalse(self.monitor.can_use(0, self.profile.skills[0]))
        self.now += .16
        self.monitor.poll()
        self.now += .16
        self.assertFalse(self.monitor.can_use(0, self.profile.skills[0]))

    def test_resolution_change_or_capture_failure_blocks_skills(self):
        self.current = Image.new("RGB", (600, 400))
        self.settle()
        self.assertIsNone(self.monitor.mana)
        self.assertFalse(self.monitor.can_use(0, self.profile.skills[0]))

    def test_gray_or_unconfigured_mana_reference_is_rejected(self):
        image = Image.new("RGB", (128, 8), (100, 100, 100))
        with self.assertRaises(ValueError):
            mana_fraction(image, image)
        self.profile.mana_reference = ""
        self.settle()
        self.assertFalse(self.monitor.can_use(0, self.profile.skills[0]))

    def test_mana_fraction_handles_full_half_and_empty_bar(self):
        reference = decode_reference(self.profile.mana_reference)
        for amount in (0, .5, 1):
            observed = region_crop(frame(mana=amount), self.profile.mana_region)
            self.assertAlmostEqual(mana_fraction(observed, reference), amount, delta=.04)

    def test_ready_reference_roundtrips_through_profile(self):
        restored = Profile.from_json(self.profile.to_json())
        self.assertEqual(restored.mana_reference, self.profile.mana_reference)
        self.assertEqual(restored.skills[0].mana_cost, 30)


if __name__ == "__main__":
    unittest.main()
