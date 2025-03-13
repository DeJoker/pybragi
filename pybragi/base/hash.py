

def djb2_hash(s: str) -> int:
    s = str(s)
    hash = 5381
    for c in s:
        hash = ((hash << 5) + hash) + ord(c)  # hash * 33 + c
    return hash & 0x7FFFFFFF  # Keep it positive

