# /app/web/consul_reg.py
import logging
import requests
import json
import sys
import socket
hostname = socket.gethostname()

def regconsul(name, ip, port, service_id, hostname):
    tag = []
    if '-stg-' in hostname:
        tag.append('weight_1')
        print(tag)
    elif "-gray-" in hostname:
        tag.append("weight_0")
        tag.append("gray")

    payload = {
            'ID' : service_id,
            'Name' : name,
            'Port' : port,
            'Address' : ip,
            'Tags' : tag,
            'Check' : {
                'http' : "http://%s:%d/healthcheck" %(ip, port),
                'Interval' : '2s',
                'Timeout' : '2s'
            }
    }

    headers = {'content-type': 'application/json'}
    regurl = 'http://127.0.0.1:8500/v1/agent/service/register'
    print(payload)

    try:
        r = requests.put(regurl,  data=json.dumps(payload), headers=headers)
        status = r.status_code
        if status == 200:
            print('INFO: reg consul %s http status: %s' %(name, status))
        else:
            print('ERROR: reg consul %s http status: %s' %(name, status))
            sys.exit(3)

    except Exception as err:
        print(str(err))
        sys.exit(2)


def delconsul(name, ip, port, service_id, hostname):
    delurl = 'http://127.0.0.1:8500/v1/agent/service/deregister/%s' % service_id
    try:
        r = requests.put(delurl)
        status = r.status_code
        if status == 200:
            print('INFO: del consul %s http status: %s' %(name, status))
        else:
            print('ERROR: del consul %s http status: %s' %(name, status))
            sys.exit(3)
    except Exception as err:
        print(str(err))
        sys.exit(2)


def regconsul2(name, ip, port):
    service_id = "%s-%s-%d" %(name, ip, port)
    logging.info(f"{service_id} reg")
    regconsul(name, ip, port, service_id, hostname)


def delconsul2(name, ip, port):
    service_id = "%s-%s-%d" %(name, ip, port)
    logging.info(f"{service_id} delreg")
    delconsul(name, ip, port, service_id, hostname)



# python '/aigc-nas01/cyj/draw_guess/service/base/consul_reg.py' reg draw_guess 192.168.220.193 25990
if __name__ == '__main__':
    operation = sys.argv[1]
    name = sys.argv[2]
    ip = sys.argv[3]
    port = int(sys.argv[4])
    #env = sys.argv[5]


    #if env == 'pre':
    #    name = "pre-" + name
    service_id = "%s-%s-%d" %(name, ip, port)
    print(service_id)

    if operation == 'reg':
        regconsul(name, ip, port, service_id, hostname)
    elif operation == 'del':
        delconsul(name, ip, port, service_id, hostname)

