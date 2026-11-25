import unittest
from ymc_next.market import Candle, validate, aggregate, crosscheck

class MarketTests(unittest.TestCase):
    def setUp(self):
        self.rows = [Candle(i*60,100,103,99,102,2) for i in range(15)]
    def test_valid(self):
        self.assertEqual(validate(self.rows,900),self.rows)
    def test_gap(self):
        with self.assertRaises(ValueError):
            validate(self.rows[:4]+self.rows[5:],900)
    def test_stale(self):
        with self.assertRaises(ValueError):
            validate(self.rows,1000)
    def test_partial(self):
        with self.assertRaises(ValueError):
            validate(self.rows,899)
    def test_aggregation(self):
        self.assertEqual(len(aggregate(self.rows,5)),3)
        self.assertEqual(len(aggregate(self.rows,10)),1)
        self.assertEqual(aggregate(self.rows,15)[0].volume,30)
    def test_crosscheck(self):
        self.assertTrue(crosscheck(100,100.1))
        self.assertFalse(crosscheck(100,101))

if __name__ == "__main__":
    unittest.main()
