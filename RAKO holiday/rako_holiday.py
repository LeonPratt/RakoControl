import socket

import http.client


UDP_IP = "0.0.0.0"
BRIDGE_IP = '192.168.1.34'
PORT = 9761
URL = 'http://' + BRIDGE_IP +'/rako.xml'

import xmltodict
import urllib.request

xml = ""
weburl=urllib.request.urlopen(URL)
if(weburl.getcode() == 200):
    xml=weburl.read()

dict=xmltodict.parse(xml)

xrooms={}

for room in dict['rako']['rooms']['Room'] :
    if room['@id'] == '0':
        continue
    room_name = room["Title"].replace(" ", "_")

    print(room)

    print(room['@id'],room_name)

    xrooms[int(room['@id'])]=room_name


def send():
    #HTTP = http.client.HTTPConnection("0.0.0.0", 8080)
    #HTTP.set_tunnel(URL)
  
    data = bytes.fromhex('5207001700310102AE')
    #HTTP.request(str(data), URL)
    #print("FOO BAR")


    soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
    soc.connect((BRIDGE_IP, PORT))
    soc.send(data)
    soc.close()


#send()

def recieve():
    
    soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)

    soc.bind((UDP_IP, PORT))

    
   
    while True:
        log_file = open("log.txt", "a")
        data, addr = soc.recvfrom(1024)
        #print("recieved message:", addr, data)
        if addr[0] != BRIDGE_IP:
            continue

        #print(addr, len(data), data[0], data[0] == 0x53)

        if len(data) >=9 and data[0] == 0x53 :

            room = data[2] * 256 + data[3]
            channel = data[4]
            command= data[5]
            val = data[7]

            

            
            if command == 0x31:
                crc = 0
                for b in data[2:]:
                    crc += b
                if crc == 256:
                    try:
                        roomname = xrooms[room]
                    except:
                        roomname = "__"
                    entry = "room=%d %s channel=%d command=%d value = %d" % (room, roomname,channel,command,val)
                    print(entry)
                    log_file.write("\n"+ entry)
                    # log = log_file.write(entry)
                else:
                    print("ZZZ", data)
            else:
                print("YYY", data)

        else:
            print("XXX", data)
        log_file.close()

recieve()


