import logging
import threading
import json
import base64
from random import randint
import os
from subprocess import Popen

class DeviceHandler:
    logger = logging.getLogger()

    def __init__(self, config):
        self.service = None
        self.tunnel = None
        self.config = config
        
    def start(self):
        self.logger.info("starting device handler")
        threading.Timer(7, self.test).start()
    
    def getMessagePayload(self):
        self.logger.debug("Preparing client->device message payload")
        payload = json.dumps({'values':{'t1':randint(0,1000), 't2':randint(0,1000)}})
        return payload
        
    def handleServerCall(self, payload):
        self.logger.info("Handling server callback with payload {0}".format(payload))
        payloadDict = json.loads(payload)
        if "command" in payloadDict:
            command = payloadDict["command"]
            self.logger.info("Received command: {0}".format(command))
            if command == "blink":
                self.logger.info("BLINK!!!")
            elif command == "reboot":
                self.logger.info("REBOOT!!!")
            elif command == "photo":
                self.logger.info("PHOTO!!!")
                photoFile = "/home/pi/puszcz.jpg"
                with open(photoFile, mode='rb') as file:
                    photoData = file.read()
                    base64data = base64.b64encode(photoData)
                    self.service.sendMessage(json.dumps({'image':base64data, 'type':'jpg'}))   
            elif command == "tunnel":
                if self.tunnel:
                    self.logger.warning("Tunnel already active - ingoring command")
                else:
                    remotePort = payloadDict.get("remotePort", 18888)
                    localPort = payloadDict.get("localPort", 22)
                    addr = payloadDict["addr"]
                    self.startTunnel(remotePort, localPort, addr) 
            elif command == "tunnel-close":
                if self.tunnel:
                    self.logger.info("terminating tunnel process")  
                    self.tunnel.terminate()
                    self.tunnel = None 
                else:
                    self.logger.warning("no tunnel process active, ignoring command")                
            else:
                self.logger.info("Command '{0}' unknown".format(command))
                
    def startTunnel(self, remotePort, localPort, addr):
        sshPrivateKeyFile = self.config.get('client', 'sshPrivateKeyFile')
        self.logger.info("Opening SSH tunneling session for remotePort={0}, localPort={1}, addr={2} using privateKey={3}".format(remotePort, localPort, addr, sshPrivateKeyFile))
        cmd = "/usr/bin/ssh -o BatchMode=yes -o StrictHostKeyChecking=no -i {0} -N -R {1}:localhost:{2} {3}".format(sshPrivateKeyFile, remotePort, localPort, addr)
        self.logger.info("Starting process: {0}".format(cmd))
        self.tunnel = Popen(cmd.split())
        self.logger.info("SSH tunneling process started")
        
    def test(self):
        self.service.sendMessage(json.dumps({'values':{'t3':randint(0,1000), 't4':randint(0,1000)}}))