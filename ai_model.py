# ai_model.py (v2) — RobustScaler + geniş özellik + özel eşik
import pandas as pd, numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler
from sklearn.metrics import classification_report, confusion_matrix
from joblib import dump

df = pd.read_csv("data/events.csv")

feat = [
    "voltage","current","power_kw","energy_kwh","temp_c","enc",
    "dt","d_power","d_energy","power_ma3","power_z"
]

# dt/delta kolonlarında NaN olabilir; dolduralım
for c in ["dt","d_power","d_energy","power_z"]:
    if c in df.columns:
        df[c] = df[c].fillna(0)

# Eğitim sadece NORMAL
train = df[df["label"]=="NORMAL"].copy()
X_train = train[feat].values

# Ölçekleme
scaler = RobustScaler()
X_train_s = scaler.fit_transform(X_train)

# Model — recall’ı artırmak için contamination’ı yükseltiyoruz (ince ayar yapılabilir)
model = IsolationForest(
    n_estimators=300,
    contamination=0.12,   # 0.10–0.15 aralığını deneyebilirsin
    random_state=42
).fit(X_train_s)

# Tüm veri üstünde değerlendirme (yalnızca rapor için)
X_all_s = scaler.transform(df[feat].values)
y_true = (df["label"]=="ANOMALY").astype(int).to_numpy()

# Decision scores: büyük skor => daha normal
scores = model.decision_function(X_all_s)

# Hedef: anomali recall'ı yükseltmek. Eşik için yüzdelik seçelim.
# Örn, en düşük %12 skoru anomali kabul (contamination ile uyumlu)
th = np.percentile(scores, 12)  # 12 == contamination*100
y_pred = (scores < th).astype(int)  # 1=anomali

print("=== Confusion Matrix (0=normal,1=anomali) ===")
print(confusion_matrix(y_true, y_pred))
print("\n=== Classification Report ===")
print(classification_report(y_true, y_pred, digits=3))

# Kaydet: hem scaler hem model hem eşik
import pickle
bundle = {"scaler": scaler, "model": model, "threshold": float(th), "features": feat}
with open("data/ai_model.joblib", "wb") as f:
    pickle.dump(bundle, f)

print("[OK] Saved model bundle to data/ai_model.joblib")
