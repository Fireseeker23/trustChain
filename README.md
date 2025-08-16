# trustChain


##  Factors Considered

### 1. **On-Time Repayment Rate (`on_time_repayment_rate`)**

* Measures how consistently the wallet repays borrowed funds on time.
* **< 50% repayment rate** → minimal credit.
* **Closer to 100%** → higher points.
* Function used = Normalize_01

---

### 2. **Default Count (`default_count`)**

* Tracks the number of loan defaults.
* **0 defaults** → maximum points.
* **Few defaults** → partial penalty.
* **Many defaults** → heavy penalty.
* Function used = points_default_count

---

### 3. **Average Transaction Frequency (`avg_tx_frequency`)**

* Reflects wallet activity.
* **Normal activity** → rewarded.
* **Very low activity** → inactivity penalty.
* **Extremely high activity** → potential suspicious behavior penalty.
* Function used = Normalize_01

---

### 4. **Average Balance (USD) (`avg_balance_usd`)**

* Higher balances indicate stronger financial capacity.
* Uses **logarithmic scaling** to prevent excessively high balances from skewing the score.
* Function used = log_norm

---

### 5. **Stablecoin Ratio (`stablecoin_ratio`)**

* Measures the share of wallet assets held in stablecoins.
* **Higher stablecoin holdings** → reduced volatility risk.
* Rewarded using a **sigmoid function** for non-linear benefits.
* Function used = stablecoin_score

---

### 6. **Debt Utilization (`debt_utilization`)**

* Ratio of borrowed funds to available funds.
* **Moderate utilization** → acceptable.
* **High utilization** → strong penalty.
* Penalization is **non-linear** for extreme cases.
* Function used = Normalize_01

---

### 7. **Staking Amount (ETH) (`staking_amount_eth`)**

* Represents ETH staked, showing long-term commitment.
* Uses **logarithmic scaling** to reward staking.
* Prevents extremely high stakes from dominating the score.
* Function used = log_norm

---

##  Scoring Method

1. **Normalization**

   * Continuous metrics are scaled to a `0–1` range.
   * Logarithmic and sigmoid transformations are applied to better model risk patterns.

2. **Weighted Sum**

   * Each factor is multiplied by a predefined weight based on importance.
   * Final score = Σ (factor × weight).

3. **Dynamic Penalties & Bonuses**

   * **Defaults** → progressively penalized.
   * **Stablecoin Ratio** → rewarded non-linearly.
   * **Debt Utilization** → penalized aggressively at higher levels.

---
**Weights**  
weights = {  
    "on_time_repayment_rate": 25,  
    "default_count": 25,  
    "avg_tx_frequency": 10,  
    "avg_balance_usd": 10,  
    "stablecoin_ratio": 10,  
    "debt_utilization": 10,  
    "staking_amount_eth": 10,  
}  

## Functions Explained

### 1. **Linear Normalization**
```python
def normalize_01(x, lo, hi):
    if hi <= lo: return 0.0
    x = max(lo, min(hi, x))
    return (x - lo) / (hi - lo)
```  
Formula -> Normalized = (x-lo)/(hi-lo)  

### 2. **Stablecoin Sigmoid Function**  
```python  
def stablecoin_score(ratio):
    return 1 / (1 + 2**(-5*(ratio - 0.5)))
```  
Formula (Logistic curve) -> 1/((1+2^[-5(ratio-0.5)]))  

### 3. **Logarithmic Normalization** 
```python  
def log_norm(x, max_val):
    return math.log(1 + x) / math.log(1 + max_val)
```
Formula -> normalized = ln(1+x)/ln(1+max_val)

### 4. **Debt Utilization Penalty** 
```python  
1 - normalize_01(factors["debt_utilization"], 0, 1)**1.5
```
Penalizes higher debt utilization.
Steps:
Normalize utilization between 0–1.
Raise to power 1.5 → harsher penalty at high utilization.
Subtract from 1 → flips scale so low utilization = safe, high utilization = risky.

### 5. **points_default_count** 
```python  
if x == 0:
  return 25
elif x <= 2:
  return 15
else:
  return max(0, 25 - x*5)
```
Assigns points based on the number of defaults:  
0 defaults → 25 points (maximum reward).  
1–2 defaults → 15 points (partial penalty).  
more than 2 defaults → progressively decreasing score (25 - x*5, floored at 0).  
Effect:  
Rewards wallets with a clean history.  
Small penalties for a few defaults.  
Heavy penalties as defaults increase.  




