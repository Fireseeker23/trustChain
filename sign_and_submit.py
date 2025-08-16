import os, time, json
from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_utils import to_hex
from web3 import Web3
from merkle import merkle_root

from dataExtractor import extract_wallet_factors
from dataExtractor import EtherscanClient

from dotenv import load_dotenv
import math

load_dotenv()
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY") 

api = EtherscanClient(ETHERSCAN_API_KEY)
factors = extract_wallet_factors("0xC6093Fd9cc143F9f058938868b2df2daF9A91d28", api=api)
print(factors)


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
    # ratio 0-1, sigmoid towards 1 if more stablecoin
    return 1 / (1 + 2**(-5*(ratio - 0.5)))

def log_norm(x, max_val):
    return math.log(1 + x) / math.log(1 + max_val)

score = 0
score += weights["on_time_repayment_rate"] * normalize_01(factors["on_time_repayment_rate"], 0.5, 1) 
score += points_default_count(factors["default_count"])
score += weights["avg_tx_frequency"] * normalize_01(factors["avg_tx_frequency"], 0, 4)  
score += weights["avg_balance_usd"] * log_norm(factors["avg_balance_usd"], 4400)  
score += weights["stablecoin_ratio"] * stablecoin_score(factors["stablecoin_ratio"])
score += weights["debt_utilization"] * (1 - normalize_01(factors["debt_utilization"], 0, 1)**1.5)  
score += weights["staking_amount_eth"] * log_norm(factors["staking_amount_eth"], 50)  
score = round(min(100, max(0, score)))

with open("score.json", "w") as f:
    f.write(f'{{"score": {score}}}')

#Merkle 
pairs = list(factors.items())
root_bytes = merkle_root(pairs)
root_hex = to_hex(root_bytes)


chain_id = 1
verifying_contract = os.getenv("SCORE_ORACLE_ADDR", "0xCcCCccccCCCCcCCCCCCcCcCccCcCCCcCcccccccC")
attester_pk = os.getenv(
    "ATTESTER_PK",
    "0x59c6995e998f97a5a0044976f7d7b5b4fa54a1a28adce5f3d7c3c7e3d7a3e8a5"
)  
attester = Account.from_key(attester_pk).address

wallet = os.getenv("WALLET", "0x000000000000000000000000000000000000bEEF")
valid_until = int(time.time()) + 3600
nonce = int(time.time())

typed_data = {
    "types": {
        "EIP712Domain": [
            {"name": "name", "type": "string"},
            {"name": "version", "type": "string"},
            {"name": "chainId", "type": "uint256"},
            {"name": "verifyingContract", "type": "address"},
        ],
        "Score": [
            {"name": "wallet", "type": "address"},
            {"name": "score", "type": "uint256"},
            {"name": "factorsRoot", "type": "bytes32"},
            {"name": "validUntil", "type": "uint256"},
            {"name": "nonce", "type": "uint256"},
        ],
    },
    "primaryType": "Score",
    "domain": {
        "name": "CryptoCreditScore",
        "version": "1",
        "chainId": chain_id,
        "verifyingContract": verifying_contract,
    },
    "message": {
        "wallet": wallet,
        "score": score,
        "factorsRoot": root_hex,
        "validUntil": valid_until,
        "nonce": nonce,
    },
}

msg = encode_typed_data(full_message=typed_data)

signed = Account.sign_message(msg, private_key=attester_pk)

print("Attester:", attester)
print("Score:", score)
print("FactorsRoot:", root_hex)
print("ValidUntil:", valid_until, "Nonce:", nonce)
print("Signature:", signed.signature.hex())


#web3 submit
if os.getenv("RPC_URL") and os.getenv("SCORE_ORACLE_ADDR"):
    w3 = Web3(Web3.HTTPProvider(os.getenv("RPC_URL")))
    acct = w3.eth.account.from_key(os.getenv("RELAY_PK", attester_pk))
    abi = json.loads(
        '[{"inputs":[{"internalType":"address","name":"wallet","type":"address"},{"internalType":"uint256","name":"score","type":"uint256"},{"internalType":"bytes32","name":"factorsRoot","type":"bytes32"},{"internalType":"uint256","name":"validUntil","type":"uint256"},{"internalType":"uint256","name":"nonce","type":"uint256"},{"internalType":"bytes","name":"signature","type":"bytes"}],"name":"submit","outputs":[],"stateMutability":"nonpayable","type":"function"}]'
    )
    ctr = w3.eth.contract(address=Web3.to_checksum_address(verifying_contract), abi=abi)
    tx = ctr.functions.submit(
        wallet, int(score), root_hex, int(valid_until), int(nonce), signed.signature
    ).build_transaction({
        'from': acct.address,
        'nonce': w3.eth.get_transaction_count(acct.address),
        'gas': 200000,
        'maxFeePerGas': w3.to_wei('30', 'gwei'),
        'maxPriorityFeePerGas': w3.to_wei('1.5', 'gwei'),
        'chainId': chain_id,
    })
    tx_s = acct.sign_transaction(tx)
    txh = w3.eth.send_raw_transaction(tx_s.rawTransaction)
    print("Submitted tx:", txh.hex())
