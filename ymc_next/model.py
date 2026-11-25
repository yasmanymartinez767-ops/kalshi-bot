import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, balanced_accuracy_score
from xgboost import XGBClassifier
from ymc_next.features import features, targets, chronological_split

def train(candles,horizon):
    x=features(candles)
    y=targets(candles,horizon).reindex(x.index)
    valid=x.notna().all(axis=1)&y.notna()
    x,y=x.loc[valid],y.loc[valid].astype(int)
    if len(x)<3000:
        raise ValueError("Insufficient training history")
    a,b,c=chronological_split(x.index,horizon)
    for part in (a,b,c):
        if set(y.loc[part])!={0,1,2}:
            raise ValueError("Missing target class")
    model=XGBClassifier(n_estimators=200,max_depth=4,learning_rate=.04,
                        objective="multi:softprob",num_class=3,n_jobs=2,random_state=42)
    model.fit(x.loc[a],y.loc[a])
    def logits(z):
        return np.log(np.clip(model.predict_proba(z),1e-8,1))
    calibrator=LogisticRegression(max_iter=1000).fit(logits(x.loc[b]),y.loc[b])
    p=calibrator.predict_proba(logits(x.loc[c]))
    baseline=np.tile(np.bincount(y.loc[a],minlength=3)/len(a),(len(c),1))
    metrics={"log_loss":float(log_loss(y.loc[c],p,labels=[0,1,2])),
             "baseline_loss":float(log_loss(y.loc[c],baseline,labels=[0,1,2])),
             "balanced_accuracy":float(balanced_accuracy_score(y.loc[c],p.argmax(axis=1))),
             "test_samples":len(c)}
    return model,calibrator,metrics
