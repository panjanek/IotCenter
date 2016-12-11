import logging
import threading
import json
import base64
from random import randint

class DeviceHandler:
    logger = logging.getLogger()

    def __init__(self, config):
        self.service = None
        self.config = config
        
    def start(self):
        self.logger.info("starting device handler")
        threading.Timer(7, self.test).start()
    
    def getMessagePayload(self):
        self.logger.debug("Preparing client->device message payload")
        payload = json.dumps({'values':{'t1':randint(0,1500), 't2':randint(0,2500), 't5':randint(0,1)}})
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
            else:
                self.logger.info("Command '{0}' unknown".format(command))
        
    def test(self):
        self.service.sendMessage(json.dumps({'values':{'t3':randint(0,1000), 't4':randint(0,1000)}}))