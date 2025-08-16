
import time
import requests
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv
from datetime import datetime
import time

load_dotenv()
# =========================
# Config (mainnet addresses)
# =========================
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")  # get from https://etherscan.io/myapikey
BASE_URL = "https://api.etherscan.io/api"

# Aave v3 Pool (Ethereum mainnet)
AAVE_V3_POOL = "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"  # ref: Aave docs/Etherscan
# Event topics
AAVE_LIQUIDATIONCALL_TOPIC = (
    "0xe413a321e8681d831f4dbccbca790d2952b56f977908e45be37335533e005286"
)  # LiquidationCall(...)

# Compound v2 cTokens (most-used)
CTOKENS = {
    "cDAI": "0x5d3a536E4D6DbD6114cc1Ead35777bAB948E3643",
    "cUSDC": "0x39AA39c021dfbaE8faC545936693aC917d5E7563",
}
# Liquidation event topic0 for Compound v2 cTokens (LiquidateBorrow)
# Signature: LiquidateBorrow(address liquidator, address borrower, uint256 repayAmount, address cTokenCollateral, uint256 seizeTokens)
# You should verify this constant before production. Tests use this value consistently.
COMPOUND_LIQUIDATEBORROW_TOPIC = (
    "0xfc6ac64d4248d985f1913f3d1b7a8dde8d52e78a9516642b76b281c5d5dbd2a7"
)

# Staking tokens
STETH = "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84"  # Lido stETH
RETH = "0xae78736Cd615f374D3085123A210448E74Fc6393"  # Rocket Pool rETH

# Stablecoins (ERC-20)
USDT = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
DAI  = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
STABLES = {"USDT": USDT, "USDC": USDC, "DAI": DAI}


# =========================
# Etherscan client (with tiny convenience layer)
# =========================
class EtherscanClient:
    def __init__(self, api_key: str, base_url: str = BASE_URL):
        self.api_key = api_key
        self.base_url = base_url

    def _get(self, params: Dict) -> Dict:
        params = {**params, "apikey": self.api_key}
        resp = requests.get(self.base_url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        # Etherscan returns status "1" for success, "0" for no results; always return a normalized shape
        if isinstance(data, dict) and "result" in data:
            return data
        return {"status": "0", "result": []}

    # --- account/txs ---
    def txlist(self, address: str, startblock: int = 0, endblock: int = 99999999, sort: str = "asc") -> List[Dict]:
        data = self._get({
            "module": "account", "action": "txlist",
            "address": address, "startblock": startblock, "endblock": endblock, "sort": sort
        })
        return data.get("result", []) if data.get("status") in ("0", "1") else []

    def erc20_transfers(self, address: str, contract_address: Optional[str] = None, sort: str = "asc") -> List[Dict]:
        params = {"module": "account", "action": "tokentx", "address": address, "sort": sort}
        if contract_address:
            params["contractaddress"] = contract_address
        data = self._get(params)
        return data.get("result", []) if data.get("status") in ("0", "1") else []

    def eth_balance(self, address: str) -> float:
        data = self._get({"module": "account", "action": "balance", "address": address, "tag": "latest"})
        if data.get("status") == "1":
            return int(data["result"]) / 1e18
        return 0.0

    def token_balance(self, token: str, address: str) -> int:
        data = self._get({
            "module": "account", "action": "tokenbalance", "contractaddress": token, "address": address, "tag": "latest"
        })
        if data.get("status") in ("0", "1"):
            # When there are no tokens held, Etherscan returns status "0" with result "0"
            try:
                return int(data.get("result", 0))
            except Exception:
                return 0
        return 0

    # --- logs ---
    def logs(self, address: str, topic0: Optional[str] = None, from_block: int = 0, to_block: str = "latest") -> List[Dict]:
        params = {
            "module": "logs", "action": "getLogs",
            "fromBlock": from_block, "toBlock": to_block, "address": address,
        }
        if topic0:
            params["topic0"] = topic0
        data = self._get(params)
        return data.get("result", []) if data.get("status") in ("0", "1") else []


# =========================
# Helpers
# =========================
def pad_topic_address(addr: str) -> str:
    """Return 32-byte topic-encoded address (lowercase, 0x + 24 zeroes + 40 hex chars)."""
    a = addr.lower()
    if a.startswith("0x"):
        a = a[2:]
    return "0x" + ("0" * 24) + a


def count_tx_calls_to(txs: List[Dict], target: str, name_contains: str) -> int:
    target_low = target.lower()
    needle = name_contains.lower()
    c = 0
    for t in txs:
        to_addr = (t.get("to") or "").lower()
        fn = (t.get("functionName") or "").lower()
        if to_addr == target_low and needle in fn:
            c += 1
    return c


def filter_logs_by_borrower(logs: List[Dict], borrower: str) -> List[Dict]:
    """Keep logs where ANY topic equals the borrower (topic-encoded)."""
    borrower_topic = pad_topic_address(borrower)
    kept = []
    for l in logs:
        topics = [t.lower() for t in l.get("topics", [])]
        if borrower_topic in topics:
            kept.append(l)
    return kept


# =========================
# Protocol extractors
# =========================
class Extractors:
    @staticmethod
    def aave_v3(address: str, api: EtherscanClient) -> Dict:
        # Count user-initiated repayments via txlist to the Pool contract
        user_txs = api.txlist(address)
        repay_count = count_tx_calls_to(user_txs, AAVE_V3_POOL, "repay(")

        # Count liquidations where the user was the borrower via logs
        liq_logs = api.logs(AAVE_V3_POOL, topic0=AAVE_LIQUIDATIONCALL_TOPIC)
        liq_logs = filter_logs_by_borrower(liq_logs, address)
        return {"repays": repay_count, "liquidations": len(liq_logs)}

    @staticmethod
    def compound_v2(address: str, api: EtherscanClient) -> Dict:
        user_txs = api.txlist(address)
        repay_count = 0
        for symbol, ctoken in CTOKENS.items():
            repay_count += count_tx_calls_to(user_txs, ctoken, "repayborrow")
            repay_count += count_tx_calls_to(user_txs, ctoken, "repayborrowbehalf")

        # Liquidations: emitted from cToken contracts targeting the borrower
        liqs = 0
        for symbol, ctoken in CTOKENS.items():
            logs = api.logs(ctoken, topic0=COMPOUND_LIQUIDATEBORROW_TOPIC)
            logs = filter_logs_by_borrower(logs, address)
            liqs += len(logs)
        return {"repays": repay_count, "liquidations": liqs}

    @staticmethod
    def staking_balances(address: str, api: EtherscanClient) -> Dict:
        steth_wei = api.token_balance(STETH, address)
        reth_wei = api.token_balance(RETH, address)
        return {"steth": steth_wei / 1e18, "reth": reth_wei / 1e18}
    
    @staticmethod
    def staking_tenure_days(address: str, api: EtherscanClient) -> int:
        txs = api.txlist(address, sort="asc")
        if not txs:
            return 0  

        address = address.lower()

        last_inbound = None
        last_outbound = None

        # track last inbound and outbound timestamps
        for tx in txs:
            ts = int(tx["timeStamp"])
            if tx["to"].lower() == address:
                last_inbound = ts
            elif tx["from"].lower() == address:
                last_outbound = ts

        if not last_inbound:
            return 0  # never staked

        # If last outbound is after last inbound, user is not staked now
        if last_outbound and last_outbound > last_inbound:
            return 0

        # Otherwise, staking is still active since last inbound
        start_date = datetime.utcfromtimestamp(last_inbound)
        days = (datetime.utcnow() - start_date).days
        return days


# =========================
# Wallet-level factor extraction
# =========================
def extract_wallet_factors(address: str, api: Optional[EtherscanClient] = None, eth_usd: Optional[float] = None) -> Dict:
    api = api or EtherscanClient(ETHERSCAN_API_KEY)

    # --- balances & activity
    eth_balance = api.eth_balance(address)
    txs = api.txlist(address)
    tx_count = len(txs)
    if tx_count:
        first_ts = int(txs[0]["timeStamp"])  # asc order
        last_ts = int(txs[-1]["timeStamp"])
        days = max(1, (last_ts - first_ts) / (60 * 60 * 24))
        avg_tx_per_day = tx_count / days
    else:
        avg_tx_per_day = 0.0

    # --- protocol interactions
    aave = Extractors.aave_v3(address, api)
    comp = Extractors.compound_v2(address, api)

    # --- staking
    stake = Extractors.staking_balances(address, api)
    staking_amount_eth = stake["steth"] + stake["reth"]
    staking_tenure = Extractors.staking_tenure_days(address, api)

    # --- stablecoin ratio (by balance weight in USD)
    usdt = api.token_balance(USDT, address) / 1e6  # 6 decimals
    usdc = api.token_balance(USDC, address) / 1e6  # 6 decimals
    dai  = api.token_balance(DAI, address)  / 1e18 # 18 decimals
    stable_usd = usdt + usdc + dai  # assume $1 pegs

    if eth_usd is None:
        # fallback so tests can inject a stable value; avoids hitting an extra endpoint
        eth_usd = 3000.0
    portfolio_usd = eth_balance * eth_usd + staking_amount_eth * eth_usd + stable_usd
    stablecoin_ratio = (stable_usd / portfolio_usd) if portfolio_usd > 0 else 0.0

    # --- repayments vs liquidations
    total_repays = aave["repays"] + comp["repays"]
    total_liqs = aave["liquidations"] + comp["liquidations"]
    on_time_repayment_rate = total_repays / max(1, (total_repays + total_liqs))

    # debt utilization would need credit line data (per-protocol); placeholder for now
    debt_utilization = 0.0

    return {
        "on_time_repayment_rate": on_time_repayment_rate,
        "default_count": total_liqs,
        "avg_tx_frequency": avg_tx_per_day,
        "avg_balance_usd": eth_balance * eth_usd,  
        "stablecoin_ratio": stablecoin_ratio,
        "debt_utilization": debt_utilization,
        "staking_amount_eth": staking_amount_eth,
        "staking_tenure_days": staking_tenure,  
        "detail": {"aave": aave, "compound": comp, "staking": stake, "stable_usd": stable_usd},
    }




if __name__ == "__main__":
    #_run_tests()
    # Example (real API):
    api = EtherscanClient(ETHERSCAN_API_KEY)
    print(extract_wallet_factors("0xf7b10d603907658f690da534e9b7dbc4dab3e2d6", api=api))
