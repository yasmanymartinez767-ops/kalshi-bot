import unittest
from ymc_next.market import Candle
from ymc_next.features import features,targets,chronological_split

class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.candles=[Candle(i*60,100+i*.01,101+i*.01,99+i*.01,100.5+i*.01,10+i%6) for i in range(150)]
    def test_causality(self):
        before=features(self.candles)
        altered=self.candles.copy()
        altered[120]=Candle(120*60,200,205,195,202,100)
        after=features(altered)
        self.assertTrue(before.loc[60*60].equals(after.loc[60*60]))
    def test_no_future_target(self):
        y=targets(self.candles,15)
        self.assertTrue(y.iloc[-15:].isna().all())
        self.assertTrue(y.iloc[:-15].notna().all())
    def test_embargo(self):
        ids=features(self.candles).index
        train,cal,test=chronological_split(ids,15)
        self.assertGreaterEqual(cal[0]-train[-1],15*60)
        self.assertGreaterEqual(test[0]-cal[-1],15*60)

if __name__=="__main__":
    unittest.main()
