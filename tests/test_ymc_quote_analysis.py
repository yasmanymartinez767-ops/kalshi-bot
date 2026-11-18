"""Regression tests for forward-only observed Kalshi exit research."""
import unittest
from scripts.ymc_analyze_kalshi_quotes import analyze, parse_price


def quote(t, ticker="KXBTC15M-TEST", yes_ask="0.20", yes_bid="0.19", no_ask="0.81", no_bid="0.80"):
    return {"observed_at_utc": f"2026-11-18T22:{t}:00+00:00",
            "ticker": ticker, "yes_ask": yes_ask, "yes_bid": yes_bid,
            "no_ask": no_ask, "no_bid": no_bid}


class OpportunityTests(unittest.TestCase):
    def test_more_than_20_cents_on_later_bid(self):
        result = analyze([quote("00"), quote("01", yes_ask="0.42", yes_bid="0.41", no_ask="0.59", no_bid="0.58")])
        self.assertEqual(result["entry_points_with_later_bid_gain_over_20c"], 1)
        self.assertEqual(result["opportunities"][0]["gross_gain_cents"], 21.0)

    def test_exactly_20_cents_does_not_qualify(self):
        result = analyze([quote("00"), quote("01", yes_ask="0.41", yes_bid="0.40", no_ask="0.61", no_bid="0.60")])
        self.assertEqual(result["entry_points_with_later_bid_gain_over_20c"], 0)

    def test_no_lookahead(self):
        result = analyze([quote("00", yes_ask="0.42", yes_bid="0.41"), quote("01", yes_ask="0.20", yes_bid="0.19")])
        self.assertEqual(result["entry_points_with_later_bid_gain_over_20c"], 0)

    def test_no_cross_contract_opportunities(self):
        result = analyze([quote("00", ticker="KXBTC15M-A"), quote("01", ticker="KXBTC15M-B", yes_ask="0.42", yes_bid="0.41")])
        self.assertEqual(result["entry_points_with_later_bid_gain_over_20c"], 0)

    def test_invalid_crossed_market_ignored(self):
        result = analyze([quote("00", yes_ask="0.18", yes_bid="0.19"), quote("01", yes_ask="0.42", yes_bid="0.41")])
        self.assertEqual(result["entry_points_with_later_bid_gain_over_20c"], 0)

    def test_max_gain_uses_earlier_ask_not_future_ask(self):
        result = analyze([quote("00", yes_ask="0.50", yes_bid="0.49"),
                          quote("01", yes_ask="0.20", yes_bid="0.19"),
                          quote("02", yes_ask="0.42", yes_bid="0.41")])
        self.assertEqual(result["best_observed_gross_gain_cents_by_contract_side"]["KXBTC15M-TEST:YES"], 21.0)

    def test_distinct_contract_count_and_elapsed_seconds(self):
        result = analyze([quote("00"), quote("01", yes_ask="0.42", yes_bid="0.41", no_ask="0.59", no_bid="0.58"),
                          quote("02", yes_ask="0.50", yes_bid="0.49", no_ask="0.51", no_bid="0.50")])
        self.assertEqual(result["contract_sides_with_at_least_one_over_20c_opportunity"], 1)
        self.assertEqual(result["first_opportunity_by_contract_side"][0]["elapsed_seconds"], 60.0)
        self.assertEqual(result["first_opportunity_by_contract_side"][0]["gross_gain_cents"], 21.0)

    def test_affordable_entry_range_is_separate(self):
        result = analyze([quote("00", yes_ask="0.20", yes_bid="0.19", no_ask="0.81", no_bid="0.80"),
                          quote("01", yes_ask="0.42", yes_bid="0.41", no_ask="0.59", no_bid="0.58")])
        self.assertEqual(result["entry_points_10_to_60c_with_later_gain_over_20c"], 1)
        self.assertEqual(result["distinct_contract_sides_10_to_60c_with_later_gain_over_20c"], 1)
        self.assertEqual(result["sample_10_to_60c_opportunities"][0]["entry_ask_cents"], 20.0)

    def test_outside_affordable_range_excluded(self):
        result = analyze([quote("00", yes_ask="0.61", yes_bid="0.60", no_ask="0.09", no_bid="0.08"),
                          quote("01", yes_ask="0.83", yes_bid="0.82", no_ask="0.17", no_bid="0.16")])
        self.assertEqual(result["entry_points_with_later_bid_gain_over_20c"], 1)
        self.assertEqual(result["entry_points_10_to_60c_with_later_gain_over_20c"], 0)

    def test_quotes_at_expiry_cannot_trigger_exit(self):
        entry = quote("00")
        entry["close_time"] = "2026-11-18T22:01:00Z"
        exit_quote = quote("01", yes_ask="0.42", yes_bid="0.41")
        exit_quote["close_time"] = "2026-11-18T22:01:00Z"
        result = analyze([entry, exit_quote])
        self.assertEqual(result["entry_points_with_later_bid_gain_over_20c"], 0)
        self.assertEqual(result["expired_quotes_excluded"], 1)

    def test_quotes_before_expiry_still_count(self):
        entry = quote("00")
        entry["close_time"] = "2026-11-18T22:02:00Z"
        exit_quote = quote("01", yes_ask="0.42", yes_bid="0.41")
        exit_quote["close_time"] = "2026-11-18T22:02:00Z"
        result = analyze([entry, exit_quote])
        self.assertEqual(result["entry_points_with_later_bid_gain_over_20c"], 1)

    def test_nonfinite_prices_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity", float("nan"), float("inf")):
            self.assertIsNone(parse_price(value))
        result = analyze([quote("00", yes_ask="NaN"), quote("01", yes_ask="0.42", yes_bid="0.41")])
        self.assertEqual(result["entry_points_with_later_bid_gain_over_20c"], 0)

    def test_yes_no_are_separate(self):
        result = analyze([quote("00", yes_ask="0.20", yes_bid="0.19", no_ask="0.20", no_bid="0.19"),
                          quote("01", yes_ask="0.42", yes_bid="0.41", no_ask="0.42", no_bid="0.41")])
        self.assertEqual(result["entry_points_with_later_bid_gain_over_20c"], 2)


if __name__ == "__main__":
    unittest.main()
