import logging
import binascii
import tornado.httpserver
import tornado.websocket
import tornado.ioloop
import tornado.web
import threading
import os
import sys
import ConfigParser
import bcrypt
import json
import time
import base64
import datetime
import database
import web
from models import DeviceModel
from collections import OrderedDict

class IotManager:
    logger = logging.getLogger()

    def __init__(self, config):
        self.service = None
        self.webServer = None
        self.config = config
        self.httpsPort = int(self.config.get('web', 'httpsPort'))
        self.httpPort = int(self.config.get('web', 'httpPort'))        
        self.adminPasswordHash = self.config.get('web', 'adminPasswordHash')
        self.apiSecret = self.config.get('web', 'apiSecret')
        self.uploadDir = self.config.get('web', 'uploadDir')
        self.dbFile = self.config.get('web', 'dbFile')
        self.httpsCertFile = self.config.get('web', 'httpsCertFile')
        self.httpsKeyFile = self.config.get('web', 'httpsKeyFile')
        self.httpsChainFile = self.config.get('web', 'httpsChainFile')
        self.localVideoPort = int(self.config.get('web', 'localVideoPort'))
        dir = os.path.dirname(os.path.realpath(sys.argv[0]))        
        self.database = database.Database(self.dbFile)
        self.deviceConfig = dict()
        for deviceId, jsonConf in dict(self.config.items('devices')).iteritems():
            self.deviceConfig[deviceId] = json.loads(jsonConf, object_pairs_hook=OrderedDict)
        self.trends = dict()
        self.lock = threading.Lock()
        
    def start(self):
        self.logger.info("starting server app handler")
        if not os.path.exists(self.uploadDir):
            os.makedirs(self.uploadDir)        
        webThread = threading.Thread(target = self.startWebServer)
        webThread.daemon = True
        webThread.start()   
        
    def handleDeviceCall(self, deviceId, payload):
        deviceIdHex = binascii.hexlify(deviceId)
        self.logger.debug("Handling request from device {0} with payload {1}".format(deviceIdHex, payload))          
        payloadDict = json.loads(payload)
        session = self.service.sessions[deviceId]        
        model = DeviceModel().loadFromSession(session, self.deviceConfig, payloadDict)
        if "image" in payloadDict:
            imageType = payloadDict.get("type", "jpg")
            imageData = base64.b64decode(payloadDict["image"])
            fn = "{0}.{1}".format(datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S'), imageType)
            imageFile = os.path.join(self.getDeviceFolder(deviceIdHex, "images"), fn)
            self.logger.info("Received {0} bytes of image data from device {1} - saving to {2}".format(len(imageData), deviceIdHex, imageFile))
            with open(imageFile, 'wb+') as f:
                f.write(imageData)             
            model.newImageUrl = "/upload/{0}/images/{1}".format(deviceIdHex, fn)
        if "values" in payloadDict:
            for variable, value in payloadDict["values"].items():
                self.database.save(deviceIdHex, variable, session.protocol, session.clientAddr[0], session.lastUpdateTime, value)
        self.webServer.websocketSend(model.toJSON())
        with session.lock:
            model.saveTrends(self.trends)
            model.computeTrends(self.trends)
        
    def startWebServer(self):
        self.webServer = web.WebServer(self, self.httpsPort, self.httpPort, self.uploadDir, self.adminPasswordHash, self.httpsCertFile, self.httpsKeyFile, self.httpsChainFile, self.localVideoPort)
        self.webServer.start()
        
    def getDeviceFolder(self, deviceId, folder):
        deviceFolder = os.path.join(self.uploadDir, deviceId)
        if not os.path.exists(deviceFolder):
            os.makedirs(deviceFolder)
        dir = os.path.join(deviceFolder, folder)  
        if not os.path.exists(dir):
            os.makedirs(dir)     
        return dir  

    def getOnlineDevices(self):
        devices = [DeviceModel().loadFromSession(session, self.deviceConfig, json.loads(session.lastPayload)).loadImages(self.getDeviceFolder(binascii.hexlify(deviceId), "images"), 6).computeTrends(self.trends) for deviceId, session in self.service.sessions.items()]
        return devices
        
    def getAllDevices(self):
        self.logger.debug("Loading devices data from DB")    
        devicesData = self.database.getDevicesData()
        devices = [DeviceModel().loadFromDict(devDict, self.deviceConfig).loadImages(self.getDeviceFolder(binascii.hexlify(deviceId), "images"), 6) for deviceId, devDict in devicesData.items()]      
        return devices
        
    def getDevice(self, deviceIdHex, imagesCount):
        deviceId = str(bytearray.fromhex(deviceIdHex))
        deviceModel = DeviceModel()
        if deviceId in self.service.sessions:
            session = self.service.sessions[deviceId]
            deviceModel.loadFromSession(session, self.deviceConfig, json.loads(session.lastPayload))
            deviceModel.loadImages(self.getDeviceFolder(deviceIdHex, "images"), imagesCount)
            deviceModel.loadCommands(self.deviceConfig)
            deviceModel.computeTrends(self.trends)            
            return deviceModel
        else:
            devicesData = self.database.getDevicesData()
            if deviceIdHex in devicesData:
                devDict = devicesData[deviceIdHex]
                deviceModel.loadFromDict(devDict, self.deviceConfig)
                deviceModel.loadImages(self.getDeviceFolder(deviceIdHex, "images"), imagesCount)
                deviceModel.loadCommands(self.deviceConfig)
                return deviceModel
            else:
                return None
                
    def sendCommand(self, deviceId, cmdConfigKey):
        cmdConf = self.deviceConfig[deviceId]["commands"][cmdConfigKey]
        payload = {}
        for attr, val in cmdConf.items():
            if attr != "label" and attr != "icon" and attr != "confirm":
                payload[attr] = val
        payloadStr = json.dumps(payload)
        deviceIdHex = deviceId
        deviceIdBin = str(bytearray.fromhex(deviceIdHex))
        self.logger.info("Sending message {0} to device {1}".format(payloadStr, deviceIdHex))
        self.service.sendMessage(deviceIdBin, payloadStr)
