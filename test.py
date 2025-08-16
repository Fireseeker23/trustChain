import pandas as pd
import math
from sklearn.metrics import mean_absolute_error, mean_squared_error



weights = {
    "on_time_repayment_rate": 25,
    "default_count": 25,
    "avg_tx_frequency": 10,
    "avg_balance_usd": 10,
    "stablecoin_ratio": 10,
    "debt_utilization": 10,
    "staking_amount_eth": 10,
}

def points_default_count(x):
    if x == 0:
        return 25
    elif x <= 2:
        return 15
    else:
        return max(0, 25 - x*5)

def normalize_01(x, lo, hi):
    if hi <= lo: return 0.0
    x = max(lo, min(hi, x))
    return (x - lo) / (hi - lo)

def stablecoin_score(ratio):

    return 1 / (1 + 2**(-5*(ratio - 0.5)))

def log_norm(x, max_val):
    return math.log(1 + x) / math.log(1 + max_val)

df = pd.read_csv("offchain/synthetic_credit_scores2.csv")


# df = df.rename(columns={
#     "Defaults": "default_count",
#     "On-time Repayment Rate": "on_time_repayment_rate",
#     "Avg Tx Frequency": "avg_tx_frequency",
#     "Balance (USD)": "avg_balance_usd",
#     "Stablecoin Ratio": "stablecoin_ratio",
#     "Debt Utilization": "debt_utilization",
#     "Staking ETH": "staking_amount_eth"
# })

def compute_score(factors, weights):
    score = 0
    score += weights["on_time_repayment_rate"] * normalize_01(factors["on_time_repayment_rate"], 0.5, 1) 
    score += points_default_count(factors["default_count"])
    score += weights["avg_tx_frequency"] * normalize_01(factors["avg_tx_frequency"], 0, 4)  
    score += weights["avg_balance_usd"] * log_norm(factors["avg_balance_usd"], 4400)  
    score += weights["stablecoin_ratio"] * stablecoin_score(factors["stablecoin_ratio"])
    score += weights["debt_utilization"] * (1 - normalize_01(factors["debt_utilization"], 0, 1)**1.5)  
    score += weights["staking_amount_eth"] * log_norm(factors["staking_amount_eth"], 50) 
    return score

df["model_score"] = df.apply(lambda row: compute_score(row, weights), axis=1)

df["error"] = df["model_score"] - df["credit_score"]
print(df[["User", "credit_score", "model_score", "error"]])




mae = mean_absolute_error(df["credit_score"], df["model_score"])
mse = mean_squared_error(df["credit_score"], df["model_score"])
print("MAE:", mae,)
