from Crypto.Cipher import AES # pip install pycryptodome
# python -c "import importlib.metadata; dists = importlib.metadata.packages_distributions(); print(dists.get('Crypto'))" # ['pycryptodome', 'pycryptodome']
import base64


def pkcs5_pad(data, block_size):
    """PKCS5 padding"""
    padding_length = block_size - (len(data) % block_size)
    padding = bytes([padding_length]) * padding_length
    return data + padding


def pkcs5_unpad(data):
    """PKCS5 unpadding"""
    padding_length = data[-1]
    return data[:-padding_length]


def base64_url_safe_encode(data):
    """Convert to Base64 URL Safe encoding"""
    base64_str = base64.b64encode(data).decode('utf-8')
    # Replace standard Base64 characters with URL-safe ones and remove padding
    safe_str = base64_str.replace('/', '_').replace('+', '-').replace('=', '')
    return safe_str


def base64_url_safe_decode(encoded_str):
    """Decode Base64 URL Safe encoded string"""
    # Add padding if necessary
    padding = 4 - (len(encoded_str) % 4) if len(encoded_str) % 4 else 0
    encoded_str = encoded_str + ('=' * padding)
    # Restore standard Base64 characters
    encoded_str = encoded_str.replace('_', '/').replace('-', '+')
    
    try:
        return base64.b64decode(encoded_str)
    except Exception as e:
        print(f"Decode failed, encoded_str: {encoded_str}, error: {e}")
        return None


def aes_encrypt(src, key):
    """AES/ECB/PKCS5 encryption, returns Base64UrlSafeEncode string"""
    if not src:
        print("src content empty!")
        return None
    
    # Convert inputs to bytes if they're strings
    if isinstance(src, str):
        src = src.encode('utf-8')
    if isinstance(key, str):
        key = key.encode('utf-8')
        
    # Create cipher
    cipher = AES.new(key, AES.MODE_ECB)
    
    # Pad data and encrypt
    padded_data = pkcs5_pad(src, AES.block_size)
    encrypted_data = cipher.encrypt(padded_data)
    
    # Encode to Base64 URL Safe
    return base64_url_safe_encode(encrypted_data)


def aes_decrypt(encrypted_str, key):
    """AES/ECB/PKCS5 decryption"""
    if isinstance(key, str):
        key = key.encode('utf-8')
        
    # Decode Base64 URL Safe
    encrypted_data = base64_url_safe_decode(encrypted_str)
    if not encrypted_data:
        return None
    
    # Create cipher
    cipher = AES.new(key, AES.MODE_ECB)
    
    # Decrypt and unpad
    decrypted_data = cipher.decrypt(encrypted_data)
    unpadded_data = pkcs5_unpad(decrypted_data)
    
    return unpadded_data.decode('utf-8')

