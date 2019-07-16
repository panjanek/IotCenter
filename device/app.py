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

class DeviceHandler:
    logger = logging.getLogger()

    def __init__(self, config):
        self.service = None
        self.tunnel = None
        self.video = None
        self.config = config
        self.first = True
        self.counter = 1;
        self.uploadfile = '/tmp/upload.txt' 
        
    def start(self):
        self.logger.info("starting device handler")
    
    def getMessagePayload(self):
        self.logger.debug("Preparing client->device message payload")
        gputemp = os.popen("vcgencmd measure_temp").readline().replace("temp=","").replace("'C","")
        cputemp = os.popen("cat /sys/class/thermal/thermal_zone0/temp").readline()
        payloadDict = {"values":{}}
        payloadDict["mid"] = self.counter
        self.counter += 1
        payloadDict["values"]["status"] = 1
        payloadDict["values"]["gpu_temp"] = float(gputemp)
        payloadDict["values"]["cpu_temp"] = float(cputemp) / 1000
        log = self.getLogToUpload()
        if log is not None:
            payloadDict["log"] = log
        payload = json.dumps(payloadDict)
        return payload
        
    def getLogToUpload(self):
        log = None
        if self.first:
            self.first = False
            with open(self.uploadfile, "a") as upfile:
                upfile.write("First message, communucation started\n")  
           
        uploadfiletmp = self.uploadfile + ".tmp"        
        if os.path.exists(self.uploadfile) and os.path.getsize(self.uploadfile) > 0:
            with open(self.uploadfile, 'r+') as upfile:
                content = upfile.read()  
                upfile.truncate(0)
            self.logger.info("found log data to upload: {0}, moving to {1}".format(content, uploadfiletmp))
            
            with open(uploadfiletmp, "a") as tmpfile:
                tmpfile.write(content)                
        
        if os.path.exists(uploadfiletmp) and os.path.getsize(uploadfiletmp) > 0:    
            with open(uploadfiletmp, 'r') as tmpfile:
                toupload = tmpfile.read() 
                log = toupload
            
        return log     
        
    def handleServerCall(self, payload):
        self.logger.info("Handling server callback with payload {0}".format(payload))
        payloadDict = json.loads(payload)
        if "ack" in payloadDict:
            mid = payloadDict["ack"]
            self.logger.info("received ack for mid {0}".format(mid))
            uploadfiletmp = self.uploadfile + ".tmp"  
            if mid == self.counter - 1 and os.path.exists(uploadfiletmp) and os.path.getsize(uploadfiletmp) > 0:
                self.logger.info("Removing file {0}".format(uploadfiletmp))
                os.remove(uploadfiletmp)
        if "command" in payloadDict:
            command = payloadDict["command"]
            self.logger.info("Received command: {0}".format(command))
            if command == "blink":
                self.logger.info("Blinking status LED")
                os.system("echo none | sudo tee /sys/class/leds/led0/trigger")
                os.system("echo 1 | sudo tee /sys/class/leds/led0/brightness")
                time.sleep(0.5)
                os.system("echo 0 | sudo tee /sys/class/leds/led0/brightness")
                time.sleep(0.5)
                os.system("echo 1 | sudo tee /sys/class/leds/led0/brightness")
                time.sleep(0.5)
                os.system("echo 0 | sudo tee /sys/class/leds/led0/brightness")
                time.sleep(0.5)
                os.system("echo 1 | sudo tee /sys/class/leds/led0/brightness")
                time.sleep(0.5)
                os.system("echo 0 | sudo tee /sys/class/leds/led0/brightness")
                time.sleep(0.5)
                os.system("echo 1 | sudo tee /sys/class/leds/led0/brightness")
            elif command == "reboot":
                self.logger.info("REBOOT!!!")
                os.system("sudo reboot")
            elif command == "photo":
                quality = payloadDict.get("quality", "sd")
                self.logger.info("Taking {0} photo".format(quality))
                photoFile = "/tmp/snapshot_{0}.jpg".format(datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S'))
                if quality == "hd":
                    os.system("raspistill -hf -t 1000 -o {0}".format(photoFile))  
                else:
                    os.system("raspistill -hf -t 1000 -w 640 -h 480 -o {0}".format(photoFile))                 
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
                    self.tunnel.kill()
                    self.tunnel = None 
                else:
                    self.logger.warning("no tunnel process active, ignoring command")         
                if self.video:
                    self.logger.info("terminating video process")  
                    self.video.kill()
                    self.video = None                        
            else:
                self.logger.info("Command '{0}' unknown".format(command))
                
    def startTunnel(self, remotePort, localPort, addr):
        sshPrivateKeyFile = self.config.get('client', 'sshPrivateKeyFile')
        self.logger.info("Opening SSH tunneling session for remotePort={0}, localPort={1}, addr={2} using privateKey={3}".format(remotePort, localPort, addr, sshPrivateKeyFile))
        cmd = "/usr/bin/ssh -o BatchMode=yes -o StrictHostKeyChecking=no -i {0} -N -R {1}:localhost:{2} {3}".format(sshPrivateKeyFile, remotePort, localPort, addr)
        self.logger.info("Starting process: {0}".format(cmd))
        self.tunnel = Popen(cmd.split())
        self.logger.info("SSH tunneling process started")
        
    def startVideo(self, port, addr):
        sshPrivateKeyFile = self.config.get('client', 'sshPrivateKeyFile')
        self.logger.info("Starting video streaming session")
        self.logger.info("loading driver bcm2835-v4l2")
        os.system("sudo modprobe bcm2835-v4l2")
        time.sleep(0.5)
        cmdVideo = "sudo motion"
        self.logger.info("Starting processes: {0}".format(cmdVideo))
        self.video = Popen(cmdVideo.split())
        cmdTunnel = "sudo /usr/bin/ssh -o BatchMode=yes -o StrictHostKeyChecking=no -i {0} -N -R {1}:localhost:8081 {2}".format(sshPrivateKeyFile, port, addr)
        self.logger.info("Starting processes: {0}".format(cmdTunnel))
        self.tunnel = Popen(cmdTunnel.split())
        self.logger.info("SSH video tunneling session started")       
