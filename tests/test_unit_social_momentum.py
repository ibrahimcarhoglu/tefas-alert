import unittest

from social_momentum import (
    classify_radar_label,
    classify_social_text,
    extract_fund_codes,
    score_social_candidate,
)


class SocialMomentumTests(unittest.TestCase):
    def test_code_extraction_requires_explicit_tag_or_fund_context(self):
        valid = {"KDE", "CPU", "ALT"}
        self.assertEqual(extract_fund_codes("$KDE ve #CPU konuşuluyor", valid), {"KDE", "CPU"})
        self.assertEqual(extract_fund_codes("ALT bugün güzel bir kelime", valid), set())
        self.assertEqual(extract_fund_codes("ALT fon için analiz", valid), set())
        self.assertEqual(extract_fund_codes("#ALT fon için analiz", valid), {"ALT"})

    def test_text_intent_separates_positive_negative_and_hype(self):
        flags = classify_social_text("Bu fonu aldım, güçlü momentum var")
        self.assertTrue(flags["positive"])
        self.assertFalse(flags["negative"])
        hype = classify_social_text("All in yüklendim, kesin yükselecek")
        self.assertTrue(hype["hype"])
        negative = classify_social_text("Balon mu, satmalı mıyım?")
        self.assertTrue(negative["negative"])

    def test_social_score_is_bounded_and_confirmed_interest_is_labeled(self):
        observation = {
            "mention_count": 8, "unique_accounts": 7, "positive_count": 6,
            "negative_count": 0, "hype_count": 0, "analytical_count": 7,
            "trusted_count": 2,
        }
        technical = {"momentum_score": 90, "trend_score": 100, "flow_score": 85}
        scores = score_social_candidate(observation, technical, baseline_mentions=2, investor_percentile=90)
        self.assertGreaterEqual(scores["score"], 65)
        self.assertLessEqual(scores["score"], 100)
        self.assertEqual(classify_radar_label(8, scores), "TEYİTLİ İLGİ")

    def test_hype_without_confirmation_is_not_a_buy_like_label(self):
        observation = {
            "mention_count": 6, "unique_accounts": 5, "positive_count": 4,
            "negative_count": 0, "hype_count": 5, "analytical_count": 0,
            "trusted_count": 0,
        }
        technical = {"momentum_score": 20, "trend_score": 0, "flow_score": 15}
        scores = score_social_candidate(observation, technical, baseline_mentions=1, investor_percentile=20)
        self.assertEqual(classify_radar_label(6, scores), "AŞIRI HYPE")

    def test_silent_rise_requires_technical_and_flow_confirmation(self):
        scores = score_social_candidate(
            {}, {"momentum_score": 90, "trend_score": 100, "flow_score": 80},
            baseline_mentions=0, investor_percentile=80,
        )
        self.assertEqual(classify_radar_label(0, scores), "SESSİZ YÜKSELİŞ")


if __name__ == "__main__":
    unittest.main()
