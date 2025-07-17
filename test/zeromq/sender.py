from random import randrange
import zmq
import time
from pybragi.base import time_utils
import logging

# Request-Reply 
def server():
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind("tcp://*:5555")

    while True:
        #  Wait for next request from client
        message = socket.recv()
        logging.info("Received request: %s" % message)

        #  Do some 'work'
        time.sleep(1)

        #  Send reply back to client
        socket.send(b"World")



# Publish/Subscribe
def publish():
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind("tcp://*:5556")

    while True:
        zipcode = randrange(1, 100000)
        temperature = randrange(-80, 135)
        relhumidity = randrange(10, 60)

        socket.send_string("%i %i %i" % (zipcode, temperature, relhumidity))




def subscribe():
    #  Socket to talk to server
    context = zmq.Context()
    socket = context.socket(zmq.SUB)

    print("Collecting updates from weather server...")
    socket.connect("tcp://localhost:5556")

    # Subscribe to zipcode, default is NYC, 10001
    zip_filter = sys.argv[1] if len(sys.argv) > 1 else "10001"

    # Python 2 - ascii bytes to unicode str
    if isinstance(zip_filter, bytes):
        zip_filter = zip_filter.decode('ascii')
    socket.setsockopt_string(zmq.SUBSCRIBE, zip_filter)

    # Process 5 updates
    total_temp = 0
    for update_nbr in range(5):
        string = socket.recv_string()
        zipcode, temperature, relhumidity = string.split()
        total_temp += int(temperature)

    logging.info(
        "Average temperature for zipcode '%s' was %dF"
        % (zip_filter, total_temp / (update_nbr + 1))
    )



# Push/Pull pipeline
def push():
    context = zmq.Context()
    socket = context.socket(zmq.PUSH)
    socket.bind("tcp://*:5557")

    while True:
        socket.send(b"test")
        logging.info("已发送")
        time.sleep(1)
