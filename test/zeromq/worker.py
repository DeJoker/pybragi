import zmq
from pybragi.base import time_utils
import logging



# Request-Reply 
def client():
    context = zmq.Context()

    #  Socket to talk to server
    logging.info("Connecting to hello world server…")
    socket = context.socket(zmq.REQ)
    socket.connect("tcp://localhost:5555")
    socket.send(b"Hello")
    #  Get the reply.
    message = socket.recv()
    logging.info(f"Received reply [ {message} ]")


# Publish/Subscribe
def subscribe():
    context = zmq.Context()
    socket = context.socket(zmq.SUB)

    logging.info("Collecting updates from weather server...")
    socket.connect("tcp://localhost:5556")

    zip_filter = "10001"

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

# Push/Pull  pipeline
# only one worker receive task


#  pusher -> pull -> sink
#        └- pull -┘
def pull():
    context = zmq.Context()

    recive = context.socket(zmq.PULL)
    recive.connect('tcp://127.0.0.1:5557')

    sender = context.socket(zmq.PUSH)
    sender.connect('tcp://127.0.0.1:5558')

    while True:
        data = recive.recv()
        logging.info("work1 正在转发...")
        sender.send(data)

def sink():
    context = zmq.Context()
    socket = context.socket(zmq.PULL)
    socket.bind("tcp://*:5558")

    while True:
        response = socket.recv()
        logging.info("response: %s" % response)


