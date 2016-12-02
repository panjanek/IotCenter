import logging
import threading
import json
import base64
import os
from subprocess import Popen
import glob
import time
import urllib2
import re
import string
import datetime

relay1_addr = "http://192.168.1.148"
relay_min = 3.5
relay_max = 5.0

pin_red = 7
pin_green = 3
pin_blue = 2

def led_rgb(r, g, b):
    os.system('sudo gpio mode {0} out'.format(pin_red))
    os.system('sudo gpio mode {0} out'.format(pin_green))
    os.system('sudo gpio mode {0} out'.format(pin_blue))
    os.system('sudo gpio write {0} {1}'.format(pin_red, r))
    os.system('sudo gpio write {0} {1}'.format(pin_green, g))
    os.system('sudo gpio write {0} {1}'.format(pin_blue, b))
    
def read_temp_raw():
    os.system('modprobe w1-gpio')
    os.system('modprobe w1-therm')
    base_dir = '/sys/bus/w1/devices/'
    device_folder = glob.glob(base_dir + '28*')[0]
    device_file = device_folder + '/w1_slave'
    f = open(device_file, 'r')
    lines = f.readlines()
    f.close()
    return lines
 
def read_temp():
    lines = read_temp_raw()
    while lines[0].strip()[-3:] != 'YES':
        time.sleep(0.2)
        lines = read_temp_raw()
    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos+2:]
        temp_c = float(temp_string) / 1000.0
        temp_f = temp_c * 9.0 / 5.0 + 32.0
        return temp_c

class DeviceHandler:
    logger = logging.getLogger()

    def __init__(self, config):
        self.service = None
        self.tunnel = None
        self.video = None
        self.config = config
        
    def start(self):
        self.logger.info("starting device handler")
    
    def getMessagePayload(self):
        self.logger.debug("Preparing client->device message payload")
        salon = -127
        try:
             salon = read_temp()
        except Exception as e:
             self.logger.error("error reading local temp")      
             self.logger.exception(e)
        piwnica = -127
        relay = 0
        try:
            os.system("sudo ifconfig eth0 192.168.1.101 netmask 255.255.255.0")
            txt = urllib2.urlopen(relay1_addr).read()
            lines = string.split(txt, '\n') 
            piwnica = float(lines[1])
            relay = int(lines[0])
        except Exception as e:
             self.logger.error("error reading data from {0}".format(relay1_addr))      
             self.logger.exception(e)    
        payloadDict = {"values":{}}
        payloadDict["values"]["relay"] = relay
        if salon > -127:
            payloadDict["values"]["salon"] = salon
        if piwnica > -127:
            payloadDict["values"]["piwnica"] = piwnica
        payload = json.dumps(payloadDict)
        return payload
        
    def handleServerCall(self, payload):
        self.logger.info("Handling server callback with payload {0}".format(payload))
        payloadDict = json.loads(payload)
        if "command" in payloadDict:
            command = payloadDict["command"]
            self.logger.info("Received command: {0}".format(command))
            if command == "blink":
                self.logger.info("Blinking LED")
                led_rgb(0,0,1)
                time.sleep(0.5)
                led_rgb(0,0,0)
            elif command == "reboot":
                self.logger.info("REBOOT!!!")
                os.system("sudo reboot")
            elif command == "photo":
                quality = payloadDict.get("quality", "sd")
                self.logger.info("Taking {0} photo".format(quality))
                photoFile = "/tmp/snapshot_{0}.jpg".format(datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S'))
                if quality == "hd":
                    os.system("raspistill -vf -hf -t 1000 -o {0}".format(photoFile))  
                else:
                    os.system("raspistill -vf -hf -t 1000 -w 640 -h 480 -o {0}".format(photoFile))                 
                with open(photoFile, mode='rb') as file:
                    photoData = file.read()
                    base64data = base64.b64encode(photoData)
                    self.service.sendMessage(json.dumps({'image':base64data, 'type':'jpg'}))   
            elif command == "relay":
                state = payloadDict.get("state", 1)
                self.logger.info("Changing relay state to: {0}".format(state))
                os.system("curl {0}/?relay={1}".format(relay1_addr, state))
            elif command == "light":
                state = payloadDict.get("state", 1)
                self.logger.info("Changing light state to: {0}".format(state))
                if state == 0:
                    led_rgb(0,0,0)
                else:
                    led_rgb(1,1,0)
            elif command == "tunnel":
                if self.tunnel:
                    self.logger.warning("Tunnel already active - ingoring command")
                else:
                    remotePort = payloadDict.get("remotePort", 18888)
                    localPort = payloadDict.get("localPort", 22)
                    addr = payloadDict["addr"]
                    self.startTunnel(remotePort, localPort, addr) 
            elif command == "video":
                if self.tunnel:
                    self.logger.warning("Tunnel already active - ingoring command")
                else:
                    port = payloadDict.get("port", 8081)
                    addr = payloadDict["addr"]
                    self.startVideo(port, addr)
            elif command == "tunnel-close":
                if self.tunnel:
                    self.logger.info("terminating tunnel process")  
                    self.tunnel.terminate()
                    self.tunnel = None 
                else:
                    self.logger.warning("no tunnel process active, ignoring command")         
                if self.video:
                    self.logger.info("terminating video process")  
                    self.video.terminate()
                    self.video = None                        
            else:
                self.logger.info("Command '{0}' unknown".format(command))

    def startVideo(self, port, addr):
        sshPrivateKeyFile = self.config.get('client', 'sshPrivateKeyFile')
        self.logger.info("Starting video streaming session")
        self.logger.info("loading driver bcm2835-v4l2")
        os.system("sudo modprobe bcm2835-v4l2")
        time.sleep(0.5)
        cmdVideo = "sudo motion"
        self.logger.info("Starting processes: {0}".format(cmdVideo))
        self.video = Popen(cmdVideo.split())
        cmdTunnel = "/usr/bin/ssh -o BatchMode=yes -o StrictHostKeyChecking=no -i {0} -N -R {1}:localhost:8081 {2}".format(sshPrivateKeyFile, port, addr)
        self.logger.info("Starting processes: {0}".format(cmdTunnel))
        self.tunnel = Popen(cmdTunnel.split())
        self.logger.info("SSH video tunneling session started")
                
    def startTunnel(self, remotePort, localPort, addr):
        sshPrivateKeyFile = self.config.get('client', 'sshPrivateKeyFile')
        self.logger.info("Opening SSH tunneling session for remotePort={0}, localPort={1}, addr={2} using privateKey={3}".format(remotePort, localPort, addr, sshPrivateKeyFile))
        cmd = "/usr/bin/ssh -o BatchMode=yes -o StrictHostKeyChecking=no -i {0} -N -R {1}:localhost:{2} {3}".format(sshPrivateKeyFile, remotePort, localPort, addr)
        self.logger.info("Starting process: {0}".format(cmd))
        self.tunnel = Popen(cmd.split())
        self.logger.info("SSH tunneling process started")