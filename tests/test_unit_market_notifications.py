import unittest
from unittest.mock import patch

from market_notifications import build_market_pulse, group_anomalies
from notification_cards import (
    render_anomaly_card,
    render_market_pulse_card,
    render_performance_card,
    render_rotation_card,
)


def row(code, flow, category="Hisse Senedi", market_cap=1_000_000_000, investors=1000):
    return {
        "code": code, "name": code, "category": category, "market_cap": market_cap,
        "num_investors": investors, "net_flow": flow, "flow_aum_pct": flow / market_cap * 100,
        "investor_change_pct": 2.0, "pct_change": 1.0, "momentum_score": 80,
        "trend_score": 100, "flow_score": 75, "technical_score": 88,
        "tefas_status": "İŞLEM GÖRÜYOR", "tefas_url": f"https://example.test/{code}",
    }


class MarketNotificationTests(unittest.TestCase):
    @patch("market_notifications._latest_rows")
    def test_market_pulse_excludes_money_market_and_reports_real_net(self, latest):
        latest.return_value = [
            row("AAA", 200_000_000), row("BBB", -50_000_000),
            row("PPF", 900_000_000, category="Para Piyasası"),
        ]
        payload = build_market_pulse("2026-08-28", limit=5)
        self.assertEqual(payload["gross_inflow"], 200_000_000)
        self.assertEqual(payload["gross_outflow"], -50_000_000)
        self.assertEqual(payload["net_flow"], 150_000_000)
        self.assertEqual([item["code"] for item in payload["top_inflows"]], ["AAA"])

    @patch("market_notifications._latest_rows")
    def test_anomalies_are_grouped_per_fund_and_sorted_by_severity(self, latest):
        latest.return_value = [row("AAA", 10), row("BBB", 10)]
        payload = group_anomalies([
            {"code": "AAA", "severity_rank": 1, "z_score": 3, "short_label": "PARA GİRİŞİ", "detail": "a"},
            {"code": "AAA", "severity_rank": 3, "z_score": 6, "short_label": "YATIRIMCI ARTIŞI", "detail": "b"},
            {"code": "BBB", "severity_rank": 2, "z_score": 4, "short_label": "PARA ÇIKIŞI", "detail": "c"},
        ], "2026-08-28")
        self.assertEqual([item["code"] for item in payload["anomalies"]], ["AAA", "BBB"])
        self.assertEqual(len(payload["anomalies"][0]["alerts"]), 2)

    def test_all_notification_cards_render_png(self):
        pulse = {
            "date": "2026-08-28", "gross_inflow": 10, "gross_outflow": -4, "net_flow": 6,
            "universe_count": 1, "top_inflows": [row("AAA", 10)], "top_outflows": [row("BBB", -4)],
        }
        performance_row = {
            **row("AAA", 10), "rank": 1, "performance_label": "DEVAM EDEN MOMENTUM",
            "continuation_score": 90, "return_1d": 1, "return_3d": 2,
            "return_1w": 3, "return_1m_display": 4,
        }
        anomaly_row = {
            **row("AAA", 10), "rank": 1, "severity_rank": 3, "max_zscore": 5,
            "alert_summary": "PARA GİRİŞİ", "alerts": [{"detail": "+10M TL"}],
        }
        rotation_row = {
            **row("AAA", 10), "rank": 1, "previous_status": "TUT", "current_status": "ALIM_ADAYI",
            "score": 85, "return_1m": .10, "return_3m": .20, "tefas_risk_value": 5,
            "target_weight": .10, "alis_valor": 1, "satis_valor": 2, "reasons": ["Trend güçlendi"],
        }
        payloads = [
            render_market_pulse_card(pulse),
            render_performance_card({"date": "2026-08-28", "leaders": [performance_row]}),
            render_anomaly_card({"date": "2026-08-28", "anomalies": [anomaly_row]}),
            render_rotation_card({"signal_date": "2026-08-28", "changes": [rotation_row]}),
        ]
        for data in payloads:
            self.assertTrue(data.startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main()
