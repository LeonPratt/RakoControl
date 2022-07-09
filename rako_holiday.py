#!/usr/bin/python3

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

alarm_delay = 5  # don't send pagerduty alert until alarm has been sounding for X seconds

UDP_IP = "0.0.0.0"
BRIDGE_IP = '192.168.1.34'
PORT = 9761
URL = 'http://' + BRIDGE_IP + '/rako.xml'

routing_key = 'R03DGSERQAG8S08Y18MMNQ8WSP33ND5H'
warn_routing_key = 'R03DJ1B4QUTG5NDO897WFQ2PDEUIVDSL'

path = "" # "/var/opt/data/"

hidden_rooms = {0: "Master_Control",
                50: "Front_Porch_PIR", 52: "Alarm_Interface"}

non_interactive = hidden_rooms.keys() | {33: "Front_Entrance_Pillars", 32: "Gate_Lights",
                                         34: "Kitchen_External", 35: "Garden_Path", 36: "Garden_Flower_Beds"}.keys()

warn_window = 120   # 180 min centered around sunset


def Now ():
    t = datetime.datetime.now(datetime.timezone.utc).astimezone()
    T = t.isoformat(timespec='seconds')
    return t, T

def get_room_names():
    import xmltodict
    import urllib.request

    global xrooms, interactive

    xml = ""
    weburl = urllib.request.urlopen(URL)
    if(weburl.getcode() == 200):
        xml = weburl.read()

    dict = xmltodict.parse(xml)

    xrooms = hidden_rooms
    interactive = set()
    lstRoom_num = []
    for room in dict['rako']['rooms']['Room']:
        if room['@id'] == '0':
            continue
        room_name = room["Title"].replace(" ", "_")

        # print(room)
        r = int(room['@id'])
        print("%02d %s" % (r, room_name))

        lstRoom_num.append(r)

        xrooms[r] = room_name

        if r not in non_interactive:
            interactive.add(r)


log_file = 0


def new_file():
    global log_file
    tmp = log_file
    t, T = Now()
    fn = "rako-%s.log" % T
    name = path + fn

    if sys.platform == "win32":
        name = fn.replace(":", ";")

    log_file = open(name, "w+", 1)  # line buffered
    if tmp:
        tmp.close()


alarm_set = "unset"


def check_alarm_still_set_at_0620():
    global alarm_set, log_session

    t, T = Now()
    
    print(T, "check_alarm_set_at_0620")
    if alarm_set == "night":
        alarm_set = "full"
        print(T, "alarm_set_upgrade", alarm_set)
        log_file.write("%s alarm_set_upgrade %s\n" % (T, alarm_set))
        resp = log_session.submit("Alarm set upgrade" + alarm_set, 'Elmhurst')


warn_alarm_unset = False
last_interactive, _ = Now()


def check_if_alarm_set():
    global warn_event_key, warn_alarm_unset, last_interactive

    t, T = Now()

    print(T, "check_if_alarm_set", alarm_set, last_interactive, t)
    if alarm_set == "unset" and last_interactive + datetime.timedelta(minutes=warn_window) < t:
        print(T, "alarm_unset_warning_pagerduty")
        warn_event_key = warn_event_session.trigger(
            "Alarm unset but house unoccupied", 'Elmhurst')
        warn_alarm_unset = True
    return schedule.CancelJob    # run once


obs = ephem.Observer()
obs.lat = "52.2053"
obs.long = "0.1218"


def get_sunrise_and_set():
    global obs
    global sunrise
    global sunset

    obs.date = ("%s 12:00" % datetime.date.today())

    sunrise = obs.previous_rising(ephem.Sun()).datetime().replace(
        tzinfo=datetime.timezone.utc).astimezone()
    sunset = obs.next_setting(ephem.Sun()).datetime().replace(
        tzinfo=datetime.timezone.utc).astimezone()

    t, T = Now()
    print(T, "ephem_calc", sunrise, sunset)

    check_at = sunset + datetime.timedelta(minutes=warn_window/2)
    schedule.every().day.at(check_at.astimezone().strftime(
        "%H:%M:%S")).do(check_if_alarm_set)


def listening():
    soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
    soc.bind((UDP_IP, PORT))
    soc.settimeout(1.0)

    global log_file

    holdoff = 0
    global log_session, event_key, event_session
    event_key = ''
    log_session = pdpyras.ChangeEventsAPISession(routing_key)
    event_session = pdpyras.EventsAPISession(routing_key)
    resp = ''

    global warn_event_key, warn_log_session, warn_event_session, warn_alarm_unset
    warn_event_key = ''
    warn_log_session = pdpyras.ChangeEventsAPISession(warn_routing_key)
    warn_event_session = pdpyras.EventsAPISession(warn_routing_key)

    global sunrise, sunset

    global last_interactive, alarm_set

    # play recorded events if alarm_set == "full" or warn_event_key

    while True:
        try:
            data, addr = soc.recvfrom(1024)
        except socket.timeout:
            schedule.run_pending()
            t, T = Now()
            
            if holdoff and t > holdoff:
                print(T, "send_pagerduty_trigger")
                event_key = event_session.trigger(
                    "Alarm is Sounding!", 'Elmhurst')
                holdoff = 0
            continue

        schedule.run_pending()

        try:
            #print("recieved message:", addr, len(data), data.hex())
            if addr[0] != BRIDGE_IP:
                continue

            t, T = Now()
            
            if len(data) > 10 and data[0:10] == b'RAKOBRIDGE':
                print(T, "rakobridge_dhcp", data)
                continue

            if len(data) < 7 or data[1] + 2 != len(data):
                print(T, "length_error", data)
                continue

            crc = 0
            for b in data[2:]:
                crc += b
            if crc != 256:
                print(T, "CRC_fail", data)
                continue

            ctype = data[0]
            if ctype == 0x53:  # status report
                crc = 0
                for b in data[2:]:
                    crc += b
                if crc != 256:
                    print(T, "CRC_fail", data)
                    continue

                room = data[2] * 256 + data[3]
                channel = data[4]
                command = data[5]

                if (len(data) == 9 or len(data) == 12) and command == 0x31:  # set scene
                    rate = data[6]
                    val = data[7]
                    try:
                        roomname = xrooms[room]
                    except:
                        roomname = "__"

                    # filter the ones that aren't real buttons
                    if room in interactive:
                        I = "I"
                        last_interactive = t
                        if warn_alarm_unset:
                            warn_alarm_unset = False
                            warn_event_session.resolve(warn_event_key)
                            print(T, "warn_alarm_resolve_interactive",
                                  warn_event_key)
                            log_file.write(
                                "%s warn_alarm_resolve_interactive\n" % T)
                            warn_event_key = ''
                    else:
                        I = "-"

                    risedelta = round(((t-sunrise).total_seconds())/60.0)
                    setdelta = round(((t-sunset).total_seconds())/60.0)
                    if (abs(risedelta) < abs(setdelta)):
                        xdelta = "R%+04d" % risedelta
                    else:
                        xdelta = "S%+04d" % setdelta

                    entry = "%s set_scene %s %s command=%02d room=%02d %s channel=%d scene=%d" % (
                        T, xdelta, I, command, room, roomname, channel, val)
                    print(entry)
                    log_file.write(entry + "\n")

                    if room == 52:  # alarm is room 52
                        if val == 4:   # scene 4 is Alarm is Set
                            if t.time().hour < 22 and t.time().hour > 6:
                                alarm_set = "full"
                            else:
                                # we don't really know this, but assume so for the moment and let 0620 schedule adjust
                                alarm_set = "night"

                            print(T, "alarm_set", alarm_set)
                            log_file.write("%s alarm_set\n" % T)
                            resp = log_session.submit(
                                "Alarm set " + alarm_set, 'Elmhurst')

                            if warn_alarm_unset:
                                warn_alarm_unset = False
                                warn_event_session.resolve(warn_event_key)
                                print(T, "warn_alarm_resolve", warn_event_key)
                                log_file.write("%s warn_alarm_resolve\n" % T)
                                warn_event_key = ''

                        elif val == 0:    # Alarm is unset
                            if event_key:
                                event_session.resolve(event_key)
                                print(T, "resolve", event_key)
                                log_file.write("%s alarm_resolve\n" % T)
                                event_key = ''
                            alarm_set = "unset"
                            print(T, "alarm_unset")
                            log_file.write("%s alarm_unset\n" % T)
                            resp = log_session.submit(
                                "Alarm unset", 'Elmhurst')
                            holdoff = 0

                        elif val == 1:    # Alarm sounding
                            print(T, "alarm_sounding")
                            log_file.write("%s alarm_sounding\n" % T)
                            holdoff = t + \
                                datetime.timedelta(seconds=alarm_delay)
                        else:
                            print(T, "alarm_unknown")
                            log_file.write("%s alarm_unknown\n" % T)

                elif len(data) == 7 and command == 0x0f:
                    print(T, "fade_stop", command, room, channel)
                elif len(data) == 8 and command == 0x32:
                    print(T, "fade_start", command, room, channel)
                else:
                    print(T, "status_parse_err", len(data), data.hex())
            else:
                print(T, "not_status_update", len(data), data.hex())

        except Exception as e:
            print(e)
            traceback.print_exc()

        # bottom of main while loop


new_file()
schedule.every().day.at("00:00").do(new_file)
# schedule.every().minute.at(':00').do(new_file)

get_sunrise_and_set()
schedule.every().day.at("00:00").do(get_sunrise_and_set)

schedule.every().day.at("06:20").do(check_alarm_still_set_at_0620)

"""

def ast_next_time(ref, when):
    w=dateutil.parser.parse(when)
    u=ref.astimezone().replace(hour=w.hour,minute=w.minute,second=w.second)
    if u < ref:
        u = u+dateutil.relativedelta.relativedelta(days=+1)
        u = u.replace(hour=w.hour,minute=w.minute,second=w.second)
    return u

s.enterabs(r=ast_next_time(t,"00:00"),0,get_sunrise_and_set, r)

r = datetime.datetime(2022,3,20,00,35,22,8888,tzinfo=datetime.timezone.utc)
n = ast_next_time( r, "03:35")
print( r.astimezone(), n.astimezone(), n-r)

r = datetime.datetime(2022,3,29,00,35,22,8888,tzinfo=datetime.timezone.utc)
n = ast_next_time( r, "03:35")
print( r.astimezone(), n.astimezone(), n-r)

r = datetime.datetime(2022,3,25,3,35,22,8888,tzinfo=datetime.timezone.utc)
n = ast_next_time( r, "03:35")
print( r.astimezone(), n.astimezone(), n-r)

r = datetime.datetime(2022,3,26,3,35,22,8888,tzinfo=datetime.timezone.utc)
n = ast_next_time( r, "03:35")
print( r.astimezone(), n.astimezone(), n-r)

r = datetime.datetime(2022,3,27,3,35,22,8888,tzinfo=datetime.timezone.utc)
n = ast_next_time( r, "03:35")
print( r.astimezone(), n.astimezone(), n-r)


r = datetime.datetime(2022,3,27,0,35,22,8888,tzinfo=datetime.timezone.utc)
n = ast_next_time( r, "01:35")
print( r.astimezone(), n.astimezone(), n-r)


r = datetime.datetime(2022,3,28,0,35,22,8888,tzinfo=datetime.timezone.utc)
n = ast_next_time( r, "01:36")
print( r.astimezone(), n.astimezone(), n-r)






t=datetime.datetime.now(tzinfo=datetime.timezone.utc)
u=t.astimezone().replace(hour=06,minute=20)
v=y.replace()

"""
def set_scene(room, channel, scene):
    
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


set_scene(23,0,1)



while True:
    try:
        get_room_names()
        print("interactive", interactive)
        listening()  # just restart the listening loop if there are random failures
    except Exception as e:
        print(e)
        traceback.print_exc
        t, T = Now()
        
        print(T, "exception_restart")
        time.sleep(10)




#set_scene( 23, 0, 1)