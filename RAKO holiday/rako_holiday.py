import socket
import random
import http.client
import datetime
import ephem
import time
import threading

import pdpyras

def convert_to_hex(NUMBER):

        hex_num = hex(NUMBER)
        print(type(hex_num))
        #hex_num = hex_num.split("x", 1)[1]
        print(type(hex_num))
        return hex_num

alarm_delay = 10


UDP_IP = "0.0.0.0"
BRIDGE_IP = '192.168.1.34'
PORT = 9761
URL = 'http://' + BRIDGE_IP +'/rako.xml'


import xmltodict
import urllib.request

timerCompleted = False

xml = ""
weburl=urllib.request.urlopen(URL)
if(weburl.getcode() == 200):
    xml=weburl.read()

dict=xmltodict.parse(xml)

xrooms={}
lstRoom_num = []
for room in dict['rako']['rooms']['Room'] :
    if room['@id'] == '0':
        continue
    room_name = room["Title"].replace(" ", "_")

    #print(room)

    print(room['@id'],room_name)


    lstRoom_num.append(int(room['@id']))

    xrooms[int(room['@id'])]=room_name

def listening():
    

                            

    soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)

    soc.bind((UDP_IP, PORT))

    soc.settimeout(1.0)

    obs = ephem.Observer()
    obs.lat = "52.2053"
    obs.long="0.1218"

    obs.date= ('2022/1/1 18:00')

    print( obs.previous_rising(ephem.Sun()).datetime(), obs.next_setting(ephem.Sun()).datetime() )
    global data 

    while True:
        log_file = open("log.txt", "a")
        try:
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

                
                sounding = False
                event_key = ''
                routing_key = 'R03DGSERQAG8S08Y18MMNQ8WSP33ND5H'
                log_session = pdpyras.ChangeEventsAPISession(routing_key)
                event_session = pdpyras.EventsAPISession(routing_key)
                resp = ''

                
                if command == 0x31:
                    crc = 0
                    for b in data[2:]:
                        crc += b
                    if crc == 256:
                        try:
                            roomname = xrooms[room]
                        except:
                            roomname = "__"

                        t=datetime.datetime.utcnow()

                        entry = "room=%d %s channel=%d command=%d value = %d  time = %s" % (room, roomname,channel,command,val, t.replace(tzinfo=datetime.timezone.utc).astimezone().isoformat(timespec='seconds') )
                        print(entry)
                        
                        log_file.write( entry + "\n")

                        if room == 23:

                            if val == 4:

                                print("set")
                                resp = log_session.submit("Alarm set", 'Elmhurst')

                            elif val == 0:
                                
                                if sounding == True:
                                    event_session.resolve(event_key)
                                    print("resolve", event_key)

                                print("unset")
                                resp = log_session.submit("Alarm unset", 'Elmhurst')
                                sounding = False

                            elif val == 1:
                                goingoffThread = threading.Thread(target=alarm_GoingOff, args=(4,)) 
                                goingoffThread.start()
                                sounding = True

                                if timerCompleted == True and sounding == True :
                                    event_key = event_session.trigger("Alarm is Sounding!", 'Elmhurst')
                            else:
                                print("unknown")

                    else:
                        print("ZZZ", data)
                else:
                    print("YYY", data)

            else:
                print("XXX", data)
            log_file.close()
        except:
            print(datetime.datetime.utcnow())


def alarm_GoingOff():
    timerCompleted = False
    time.sleep(alarm_delay)
    timercompleted = True

try:
    New_thread = threading.Thread(target = listening)
    New_thread.start()
except:
    print("unable to start a new thread")
    quit()

def set_scene( room, channel, scene):

    data = bytearray.fromhex('000000000000000000')

    data[0] = 0x52
    data[1] = 7
    data[2] = room >> 8
    data[3] = room & 0xff
    data[4] = channel
    data[5] = 0x31
    data[6] = 0x1
    data[7] = scene

    sum = 0
    for x in data[1:]:
        sum += x

    data[8] = 0x100 - (sum & 0xff)

    print(data)
    soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
    soc.connect((BRIDGE_IP, PORT))
    soc.send(data)
    soc.close()


#set_scene( 23, 0, 1)


