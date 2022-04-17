import datetime
import sched
import time
import socket
import logging
import os
from os import walk

from numpy import full

from threading import Thread
#enter the names of the log files
lognames = ["rako-2022-03-31.log","rako-2022-04-31.log"]

def Current_Time():

    global current_time
    while True:
        t=datetime.datetime.now(datetime.timezone.utc)
        T=t.astimezone().isoformat(timespec='seconds')
        current_time = T.split("T")[1]
        time.sleep(1)

thread = Thread(target=Current_Time)
thread.start()

def set_scene(dta):

    room = int(dta[2])
    channel = int(dta[3])
    scene =int(dta[4])


    BRIDGE_IP = "192.168.1.34"
    PORT = "9761"
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

#def playback(full_log):
#
#    info = []
#
#
#    for x in range(len(full_log)):
#        current_time = ""
#        date = full_log[x].split(" ")[0]
#        tod = date.split("T")[1] 
# 
#        splt = full_log[x].split(" ")
#        room = splt[5].split("=")[1]
#        channel = splt[7].split("=")[1]
#        scene = splt[8].split("=")[1]
#        event = splt[1]            
#        dta = (tod, event,room,channel,scene)
#        info.append(dta)            
#        continue
#    
#    yield info


def breakup_log(log):
    
    date = log.split(" ")[0]
    tod = date.split("T")[1] 
 
    splt = log.split(" ")
    room = splt[5].split("=")[1]
    channel = splt[7].split("=")[1]
    scene = splt[8].split("=")[1]
    event = splt[1]            
    dta = (tod, event,room,channel,scene)
           
    yield dta


def schedule_lights(lst):
    c = current_time.split("+")[0]
    currentdatetime = datetime.datetime.strptime(c, "%H:%M:%S")
    s = sched.scheduler(time.time,time.sleep)
    for event in lst:
        TIME = event[0]
        t = TIME.split("+")[0]
        DateTime = datetime.datetime.strptime(t, "%H:%M:%S")
        delay = (DateTime-currentdatetime).total_seconds()

        s.enter(delay,1,set_scene, argument= (event))


def strip_earlier(lst):
    
    for x in range(len(lst)):
        if lst[0][0] < current_time:
            lst.pop(0)
        elif lst[0][0] > current_time:
            break

    yield lst


def readlogs():

    logs = []

    path = r"\rako_record"
    dir_path= os.path.dirname(os.path.realpath(__name__)) + path

    filenames = next(walk(dir_path))[2]
    lognames = []
    for x in range(len(filenames)):
        if ".log" in filenames[x]:
            lognames.append(filenames[x])
    lognames.sort()


   
    global full_log
    full_log = []

    for x in range(len(lognames)):
        fn = "rako_record\\"+ lognames[x]

        f = open(fn, "r")
        file = f.readlines()
        for y in range(len(file)):

            if " I " in file[y]:
                full_log.append(file[y].strip("\n"))


    for x in range(len(full_log)):
        inf = breakup_log(full_log[x])
        logs.append(next(inf))
    inf = strip_earlier(logs)
    logs = next(inf)

    schedule_lights(logs)


while True:    
    readlogs()
    time.sleep(10)

        