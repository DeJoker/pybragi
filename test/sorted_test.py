

def get_key():
    return None, None

x = get_key()
if not x:
    print("x is None")
else:
    print("!!!!! tuple of None is not None!!!!!")  # this way

xx = [
    {"ipv4": "192.168.1.1", "port": 8080, "datetime": "2021-01-01 12:00:01"},
    {"ipv4": "192.168.1.1", "port": 8081, "datetime": "2021-01-01 12:00:02"},
    {"ipv4": "192.168.1.1", "port": 8080, "datetime": "2021-01-01 12:00:00"},
]

xx = sorted(xx, key=lambda x: f"{x['ipv4']}:{x['port']}:{x['datetime']}", reverse=True)

print(xx)

