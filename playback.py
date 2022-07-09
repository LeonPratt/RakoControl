from asyncio.windows_events import NULL
import sched
import socket
import random
import http.client
import datetime
import ephem
import time
import pdpyras
import schedule
import traceback
import sys
import os
from os import walk
from threading import Thread

TIME = ""
t=datetime.datetime.now(datetime.timezone.utc)
T=t.astimezone().isoformat(timespec='seconds')
 
     
current = str(T).split("T")[1]
current = current.split("+")[0]

t = datetime.datetime.strptime(current, "%H:%M:%S")
TIME = str(t).split(" ")[1]
        
def Current_Time():
    
    global t
    global TIME
    while True:
        t=datetime.datetime.now(datetime.timezone.utc)
        T=t.astimezone().isoformat(timespec='seconds')
 
     
        current = str(T).split("T")[1]
        current = current.split("+")[0]

        t = datetime.datetime.strptime(current, "%H:%M:%S")
        TIME = str(t).split(" ")[1]
        
        time.sleep(1)

thread = Thread(target=Current_Time)
thread.start()


def set_scene(dta):
    
    room = dta[0]
    channel = dta[1]
    scene = dta[2]

    BRIDGE_IP = "192.168.1.34"
    PORT = 9761
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

def match_time(dta):

    ct = str(schedtime).split(":")
    cs = int(ct[2]) + 1
    a = ct[0] + ":" + ct[1] + ":" + str(cs)
    while schedtime != t and a != t:
        print(schedtime," ", a," ", t)
        time.sleep(1)
 
    
    set_scene(dta)


     
    #print(len(combined_logfile))
def schedule_lights(LOG):
    for x in LOG:
        splt_cmd = x.split(" ")
        date = splt_cmd[0]
        tod = date.split("T")[1]
        room = splt_cmd[5].split("=")[1]
        channel = splt_cmd[7].split("=")[1]
        scene = splt_cmd[8].split("=")[1]
        
        t = tod.split("+")[0]
        
        global schedtime
        schedtime = datetime.datetime.strptime(t,"%H:%M:%S")
        #match_time(room,channel,scene)
        #print(schedtime, current_time)
        #delay = (schedtime-t).total_seconds()
        #s = sched.scheduler(time.time,time.sleep)
        dta = (int(room),int(channel),int(scene))
        print(dta)
        match_time(dta)
        
        
        #s.enter(delay,1,set_scene, argument= (dta))
        #print("scheduled %s for %s (%f seconds)" % (dta, str(schedtime), float(delay)))
        #match_time(room,channel,scene)
        #print(delay)



while True:
    dir_path= os.path.dirname(os.path.realpath(__name__))

    files = next(walk(dir_path))[2]


    combined_logfile = []
    for x in files:
        if ".log" in x:
            f  = open(x,"r")
            file = f.read().split("\n")
            for y in file:
                if " I " in y:
                    combined_logfile.append(y)

    def strip_earlier(lst):

        for x in range(len(lst)):
                
            tod = lst[0].split(" ")[0].split("T")[1].split("+")[0]
                #print(tod, TIME, len(TIME))
            if tod < TIME:
                
                lst.pop(0)
            else:
                break
        return lst
    LOG = strip_earlier(combined_logfile)
    schedule_lights(LOG)
