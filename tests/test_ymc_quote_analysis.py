"""Regression tests for forward-only observed Kalshi exit research."""
import unittest
from scripts.ymc_analyze_kalshi_quotes import analyze


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

    def test_yes_no_are_separate(self):
        result = analyze([quote("00", yes_ask="0.20", yes_bid="0.19", no_ask="0.20", no_bid="0.19"),
                          quote("01", yes_ask="0.42", yes_bid="0.41", no_ask="0.42", no_bid="0.41")])
        self.assertEqual(result["entry_points_with_later_bid_gain_over_20c"], 2)


if __name__ == "__main__":
    unittest.main()
