import os
import secrets
import httpx
from dotenv import load_dotenv

load_dotenv()

REGISTRATION_FEE_BTC = 0.01
OWNER_BTC_ADDRESS = os.getenv("OWNER_BTC_ADDRESS", "bc1qaxkts7gnwzxwspvzdmjn65xqvx30r2pu60ygxt")
BTCPAY_URL = os.getenv("BTCPAY_URL", "http://localhost:49392")
BTCPAY_API_KEY = os.getenv("BTCPAY_API_KEY", "")
BTCPAY_STORE_ID = os.getenv("BTCPAY_STORE_ID", "")


def get_registration_address() -> str:
    """Возвращает адрес владельца для приёма регистрационных взносов."""
    return OWNER_BTC_ADDRESS


async def create_payment_invoice(agent_id: str, btc_address: str) -> dict:
    """Создаёт invoice для оплаты регистрации. Платёж идёт на адрес владельца площадки."""
    if os.getenv("DEV_MODE") == "true" or not BTCPAY_API_KEY or BTCPAY_API_KEY == "your_btcpay_api_key":
        # Dev mode — возвращаем мок
        return {
            "invoice_id": f"mock_{secrets.token_hex(8)}",
            "pay_to": OWNER_BTC_ADDRESS,  # агент платит сюда
            "amount_btc": REGISTRATION_FEE_BTC,
            "status": "pending",
            "note": f"Send exactly {REGISTRATION_FEE_BTC} BTC to activate agent {agent_id}",
        }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BTCPAY_URL}/api/v1/stores/{BTCPAY_STORE_ID}/invoices",
            headers={"Authorization": f"token {BTCPAY_API_KEY}"},
            json={
                "amount": REGISTRATION_FEE_BTC,
                "currency": "BTC",
                "metadata": {"agent_id": agent_id},
            },
        )
        response.raise_for_status()
        data = response.json()
        return {
            "invoice_id": data["id"],
            "btc_address": btc_address,
            "amount_btc": REGISTRATION_FEE_BTC,
            "status": data["status"],
            "checkout_url": data["checkoutLink"],
        }


async def check_registration_payment(agent_id: str, expected_satoshis: int = 1_000_000) -> bool:
    """
    Проверяет оплату регистрации.
    В продакшене BTCPay Server отправит webhook при получении платежа.
    Здесь — простая проверка через blockstream.info (для MVP без BTCPay).
    """
    if os.getenv("DEV_MODE") == "true":
        return True

    # Проверяем входящие транзакции на адрес владельца
    # В продакшене лучше использовать BTCPay webhook вместо polling
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://blockstream.info/api/address/{OWNER_BTC_ADDRESS}/txs",
            timeout=10.0,
        )
        if response.status_code != 200:
            return False

        txs = response.json()
        for tx in txs:
            for vout in tx.get("vout", []):
                if (
                    vout.get("scriptpubkey_address") == OWNER_BTC_ADDRESS
                    and vout.get("value", 0) >= expected_satoshis
                ):
                    return True
        return False
