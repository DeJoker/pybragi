import time
from pybragi.zy.signature import ZyTicket

ticket = ZyTicket("nIASD91jsnfvas9y")

ticket.access_token = "1234567890"
ticket.randomString = "test"
ticket.milli_timestamp = int(time.time() * 1000)
# ticket.milli_timestamp = int(time.time() * 1000) - 500 * 1000 #$ expired in 5 minutes
ticket.user_id = "1234567890"
ticket.platform_id = 1

ticket_str = ticket.encode()
print(ticket_str)

ticket.decode(ticket_str)
print(ticket)
print(ticket.allow())