# trustChain


##  Factors Considered

### 1. **On-Time Repayment Rate (`on_time_repayment_rate`)**

* Measures how consistently the wallet repays borrowed funds on time.
* **< 50% repayment rate** → minimal credit.
* **Closer to 100%** → higher points.

---

### 2. **Default Count (`default_count`)**

* Tracks the number of loan defaults.
* **0 defaults** → maximum points.
* **Few defaults** → partial penalty.
* **Many defaults** → heavy penalty.

---

### 3. **Average Transaction Frequency (`avg_tx_frequency`)**

* Reflects wallet activity.
* **Normal activity** → rewarded.
* **Very low activity** → inactivity penalty.
* **Extremely high activity** → potential suspicious behavior penalty.

---

### 4. **Average Balance (USD) (`avg_balance_usd`)**

* Higher balances indicate stronger financial capacity.
* Uses **logarithmic scaling** to prevent excessively high balances from skewing the score.

---

### 5. **Stablecoin Ratio (`stablecoin_ratio`)**

* Measures the share of wallet assets held in stablecoins.
* **Higher stablecoin holdings** → reduced volatility risk.
* Rewarded using a **sigmoid function** for non-linear benefits.

---

### 6. **Debt Utilization (`debt_utilization`)**

* Ratio of borrowed funds to available funds.
* **Moderate utilization** → acceptable.
* **High utilization** → strong penalty.
* Penalization is **non-linear** for extreme cases.

---

### 7. **Staking Amount (ETH) (`staking_amount_eth`)**

* Represents ETH staked, showing long-term commitment.
* Uses **logarithmic scaling** to reward staking.
* Prevents extremely high stakes from dominating the score.

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

