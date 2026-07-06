import argparse
import hashlib
import hmac
import logging
import os
import sys
import time
import requests

# -------------------------------------------------------------------
# LOGGING CONFIGURATION
# -------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("trading_bot.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("BinanceFuturesBot")

# -------------------------------------------------------------------
# CLIENT / API LAYER
# -------------------------------------------------------------------
class BinanceFuturesClient:
    """Handles direct REST API communication with Binance Futures Testnet."""
    
    BASE_URL = "https://testnet.binancefuture.com"

    def __init__(self, api_key: str, api_secret: str):
        if not api_key or not api_secret:
            raise ValueError("API Key and API Secret must be provided.")
        self.api_key = api_key
        self.api_secret = api_secret
        self.headers = {
            "X-MBX-APIKEY": self.api_key
        }

    def _generate_signature(self, query_string: str) -> str:
        """Generates HMAC-SHA256 signature required by Binance API."""
        return hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def place_order(self, symbol: str, side: str, order_type: str, quantity: float, price: float = None):
        """Sends a POST request to place a market or limit order."""
        endpoint = "/fapi/v1/order"
        url = f"{self.BASE_URL}{endpoint}"
        
        # Build payload parameters
        params = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": quantity,
            "timestamp": int(time.time() * 1000)
        }
        
        if order_type.upper() == "LIMIT":
            if price is None:
                raise ValueError("Price is required for LIMIT orders.")
            params["price"] = price
            params["timeInForce"] = "GTC"  # Good 'Til Cancelled mandatory for limit

        # Create query string and sign it
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        signature = self._generate_signature(query_string)
        query_string += f"&signature={signature}"

        logger.info(f"Sending API Request to {endpoint} with payload: {params}")

        try:
            response = requests.post(url, params=query_string, headers=self.headers, timeout=10)
            response_json = response.json()
            
            logger.info(f"Received API Response Status: {response.status_code}")
            logger.debug(f"Response Payload: {response_json}")
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response_json
                }
            else:
                return {
                    "success": False,
                    "error": response_json.get("msg", "Unknown error occurred"),
                    "code": response_json.get("code", "N/A")
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error encountered: {str(e)}")
            return {
                "success": False,
                "error": f"Network Exception: {str(e)}"
            }

# -------------------------------------------------------------------
# COMMAND / CLI LAYER
# -------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Binance Futures Testnet Trading Bot CLI")
    
    parser.add_argument("--symbol", type=str, required=True, help="Trading pair symbol (e.g., BTCUSDT)")
    parser.add_argument("--side", type=str, required=True, choices=["BUY", "SELL"], help="Order side (BUY or SELL)")
    parser.add_argument("--type", type=str, required=True, choices=["MARKET", "LIMIT"], help="Order type (MARKET or LIMIT)")
    parser.add_argument("--quantity", type=float, required=True, help="Quantity to trade")
    parser.add_argument("--price", type=float, required=False, help="Price per unit (Required if type is LIMIT)")

    args = parser.parse_args()

    # Load API Keys from environment variables
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")

    if not api_key or not api_secret:
        print("\n[ERROR] Missing Authentication: Please set BINANCE_API_KEY and BINANCE_API_SECRET environment variables.\n")
        sys.exit(1)

    # Input Validation
    if args.type.upper() == "LIMIT" and args.price is None:
        parser.error("--price is required when execution --type is LIMIT")

    # 1. Print Order Request Summary
    print("\n" + "="*50)
    print("               ORDER REQUEST SUMMARY               ")
    print("="*50)
    print(f"Symbol:      {args.symbol.upper()}")
    print(f"Side:        {args.side.upper()}")
    print(f"Type:        {args.type.upper()}")
    print(f"Quantity:    {args.quantity}")
    if args.price:
        print(f"Price:       {args.price}")
    print("="*50 + "\n")

    # Initialize client and process order
    try:
        client = BinanceFuturesClient(api_key, api_secret)
        result = client.place_order(
            symbol=args.symbol,
            side=args.side,
            order_type=args.type,
            quantity=args.quantity,
            price=args.price
        )
        
        # 2. Print Execution Response Output
        print("="*50)
        print("              ACTION RESPONSE DETAILS              ")
        print("="*50)
        
        if result["success"]:
            data = result["data"]
            print(f"Status Message: SUCCESS")
            print(f"OrderID:        {data.get('orderId')}")
            print(f"Order Status:   {data.get('status')}")
            print(f"Executed Qty:   {data.get('executedQty')}")
            print(f"Avg Price:      {data.get('avgPrice', 'N/A')}")
            print("\n>>> ORDER PLACED SUCCESSFULLY <<<")
        else:
            print(f"Status Message: FAILURE")
            print(f"Error Message:  {result['error']}")
            if "code" in result:
                print(f"Error Code:     {result['code']}")
            print("\n>>> ORDER PLACEMENT FAILED <<<")
            
        print("="*50 + "\n")

    except Exception as e:
        logger.critical(f"Unhandled critical crash error: {str(e)}")
        print(f"\n[CRITICAL ERROR] Execution stopped: {str(e)}\n")

if __name__ == "__main__":
    main()
