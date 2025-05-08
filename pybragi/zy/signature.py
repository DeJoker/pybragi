import time
import traceback
from pybragi.base.crypto.ase_ecb_pkcs5 import aes_encrypt, aes_decrypt
import json

class ZyTicket:
    ticketFmtLen = 5

    # access_token@type@time@userid@platformid@deviceid@extend_data_json
    tickerFmt     = "%s@%s@%s@%s@%d@%s@%s"

    def __init__(self, key: str):
        self.access_token = ""
        self.randomString = "" # random for each ticket
        self.milli_timestamp = 0
        self.user_id = ""
        self.platform_id = 0
        self.device_id = ""
        self.extend_data_json = ""
        self.extend_data = {}
        self.key = key
    
    def decode(self, token):
        if not token:
            raise ValueError("invalid token")
            
        try:
            token_str = token.decode('utf-8') if isinstance(token, bytes) else token
            plain_text = aes_decrypt(token_str, self.key)
            if not plain_text:
                raise ValueError("decryption failed")
                
            parts = plain_text.split('@')
            if len(parts) < ZyTicket.ticketFmtLen:
                raise ValueError("token length error")
                
            self.access_token = parts[0]
            self.randomString = parts[1]

            hex_milli_ticks = parts[2]
            milli_ticks = int(hex_milli_ticks, 16)

            self.milli_timestamp = milli_ticks
            self.user_id = parts[3]
            self.platform_id = int(parts[4])
            
            if len(parts) > ZyTicket.ticketFmtLen:
                self.device_id = parts[5]
                
            if len(parts) > ZyTicket.ticketFmtLen+1:
                self.extend_data_json = parts[6]
                if self.extend_data_json:
                    self.extend_data = json.loads(self.extend_data_json)
                    
            return None
        except Exception as e:
            traceback.print_exc()
    
    def encode(self):
        ticket_str = f"{self.access_token}@{self.randomString}@{self.milli_timestamp}@{self.user_id}@{self.platform_id}@{self.device_id}@{self.extend_data_json}"
        encrypted = aes_encrypt(ticket_str, self.key)
        return encrypted
    
    def allow(self):
        if not self.access_token or not self.user_id:
            return False, "invalid ticket"
        if abs(self.milli_timestamp/1000 - int(time.time())) > 60*5: # timestamp valid in 5 minutes
            return False, "ticket expired"
        return True, None
    
    def __str__(self):
        return f"ZyTicket(access_token={self.access_token}, randomString={self.randomString}, milli_timestamp={self.milli_timestamp}, user_id={self.user_id}, platform_id={self.platform_id}, device_id={self.device_id}, extend_data={self.extend_data})"


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="core process service")
    parser.add_argument("--key", type=str, help="key")
    parser.add_argument("--ticker", type=str, help="ticker")
    args = parser.parse_args()

    ticket = ZyTicket(args.key)
    str = args.ticker
    ticket.decode(str)
    print(ticket)
    print(f"ticket.allow()={ticket.allow()}")
