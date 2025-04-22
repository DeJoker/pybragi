import hashlib
import json
import time
import base64
from typing import Dict, Tuple

class SignatureHelper:
    def __init__(self, salt: str, expire_seconds: int = 120):
        self.salt = salt
        self.expire_seconds = expire_seconds
    
    def generate_signature(self, payload_str: str, timestamp = int(time.time())) -> str:
        # 生成签名
        message = f"{payload_str}{self.salt}{timestamp}"
        signature = hashlib.sha256(message.encode()).digest()
        signature_b64 = base64.b64encode(signature).decode()
        
        return signature_b64
    
    def verify_signature(self, payload_str: str, signature: str, timestamp: int) -> bool:
        # 验证时间戳
        now = int(time.time())
        if abs(now - timestamp) > self.expire_seconds:
            return False
            
        # 验证签名
        message = f"{payload_str}{self.salt}{timestamp}"
        expected_signature = hashlib.sha256(message.encode()).digest()
        expected_signature_b64 = base64.b64encode(expected_signature).decode()
        
        return signature == expected_signature_b64

if __name__ == "__main__":
    salt="abcd1234567890"
    
    helper = SignatureHelper(salt=salt)
    signature = helper.generate_signature(salt)
    print(signature)
    print(helper.verify_signature(salt, signature, int(time.time())))
