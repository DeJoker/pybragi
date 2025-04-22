import random, string, sys
import time
import uuid
from pybragi.zy.signature import ZyTicket


if __name__ == "__main__":
    encryptionKey = "nIASD91jsnfvas9y"
    def main():
        ticket = ZyTicket(encryptionKey)
        # Example ticket data to encode
        ticket.access_token = uuid.uuid4().hex
        ticket.type = "".join(random.choices(string.digits+string.ascii_letters, k=10))
        ticket.user_id = "user123"
        ticket.milli_timestamp = int(time.time() * 1000) + 299000
        # ticket.platform_id = 1
        # ticket.device_id = "device456"
        # extend_data = {
        #     "xxxx": 101,
        #     "clientVersion": "1.0.0",
        #     "scheme": "ws"
        # }
        # ticket.extend_data_json = json.dumps(extend_data)

        # Encrypt
        encrypted = ticket.encode()
        print(f"Encoded ticket: {ticket}")
        print(f"Encrypted token: {encrypted}")
        
        # Decrypt and parse
        ticket2 = ZyTicket(encryptionKey)
        error = ticket2.decode(encrypted)
        if error:
            print(f"Error decoding ticket: {error}")
        else:
            print(f"Decoded ticket: {ticket2}")
            print(f"valid? {ticket2.allow()}")

    main()
    print("done")

