import logging
import tornado.web
import os
import binascii
import bcrypt
import json
import datetime
import urllib
import database
from models import DeviceModel
from models import SensorValue
from models import UploadedImage
from models import SensorFilter

class BaseWebHandler(tornado.web.RequestHandler):
  def isAuthenticated(self):
    user = self.get_secure_cookie("user")
    if user:
        return True
    else:
        return False        
        
class HomeWebHandler(BaseWebHandler):
    def initialize(self, service, deviceConfig, iotManager):
        self.service = service
        self.deviceConfig = deviceConfig
        self.iotManager = iotManager

    def get(self):
        if self.isAuthenticated():
            devices = [DeviceModel().loadFromSession(session, self.deviceConfig, json.loads(session.lastPayload)).loadImages(self.iotManager.getDeviceFolder(binascii.hexlify(deviceId), "images"), 6) for deviceId, session in self.service.sessions.items()]
            self.render("views/home.html", devices=devices)      
        else:
            self.redirect("/login")
            
class DevicesWebHandler(BaseWebHandler):
    logger = logging.getLogger()
    
    def initialize(self, service, deviceConfig, iotManager):
        self.service = service
        self.deviceConfig = deviceConfig
        self.iotManager = iotManager
        
    def get(self):
        if self.isAuthenticated():          
            self.logger.debug("Loading devices data from DB")
            devicesData = self.iotManager.database.getDevicesData()
            devices = [DeviceModel().loadFromDict(devDict, self.deviceConfig).loadImages(self.iotManager.getDeviceFolder(binascii.hexlify(deviceId), "images"), 6) for deviceId, devDict in devicesData.items()]              
            self.render("views/devices.html", devices=devices)               
        else:
            self.redirect("/login?"+urllib.urlencode({"returnUrl":self.request.uri}))            
            
class DeviceWebHandler(BaseWebHandler):
    logger = logging.getLogger()
    
    def initialize(self, service, deviceConfig, iotManager):
        self.service = service
        self.deviceConfig = deviceConfig
        self.iotManager = iotManager
        
    def get(self, deviceIdHex):
        if self.isAuthenticated():
            deviceId = str(bytearray.fromhex(deviceIdHex))
            imagesCount = int(tornado.escape.xhtml_escape(self.get_argument("images", "6")))
            deviceModel = DeviceModel()
            if deviceId in self.service.sessions:
                session = self.service.sessions[deviceId]
                deviceModel.loadFromSession(session, self.deviceConfig, json.loads(session.lastPayload))
                deviceModel.loadImages(self.iotManager.getDeviceFolder(deviceIdHex, "images"), imagesCount)
                deviceModel.loadCommands(self.deviceConfig)
                self.render("views/device.html", device = deviceModel, imagesCount=imagesCount)    
            else:
                devicesData = self.iotManager.database.getDevicesData()
                if deviceIdHex in devicesData:
                    devDict = devicesData[deviceIdHex]
                    deviceModel.loadFromDict(devDict, self.deviceConfig)
                    deviceModel.loadImages(self.iotManager.getDeviceFolder(deviceIdHex, "images"), imagesCount)
                    deviceModel.loadCommands(self.deviceConfig)
                    self.render("views/device.html", device = deviceModel, imagesCount=imagesCount)    
                else:
                    self.logger.warning("device {0} not found".format(deviceIdHex))            
        else:
            self.redirect("/login?"+urllib.urlencode({"returnUrl":self.request.uri}))

class HistoryWebHandler(BaseWebHandler):
    logger = logging.getLogger()

    def initialize(self, service, deviceConfig, iotManager):
        self.service = service
        self.deviceConfig = deviceConfig
        self.iotManager = iotManager

    def get(self):
        if self.isAuthenticated():
            fromTime = tornado.escape.xhtml_escape(self.get_argument("fromTime", (datetime.datetime.now() - datetime.timedelta(days=2)).strftime('%Y-%m-%d')))
            toTime = tornado.escape.xhtml_escape(self.get_argument("toTime", (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')))
            aggregation = tornado.escape.xhtml_escape(self.get_argument("aggregation", "minutes"))
            sensors = []
            chartData = []
            chartSensors = []
            showChart = False
            for deviceId, conf in self.deviceConfig.items():
                if "values" in conf:
                    for id, varConf in conf["values"].items():
                        parameterName = "{0}.{1}".format(deviceId, id)
                        selected = self.get_argument(parameterName, default=None)
                        sensorObj = SensorFilter(deviceId, conf["name"], id, varConf.get("label", id), varConf.get("type", "number"), selected)
                        sensors.append(sensorObj)
                        if selected:
                            showChart = True
                            chartSensors.append(sensorObj)
            fromTimeParsed = datetime.datetime.strptime(fromTime, '%Y-%m-%d')
            toTimeParsed = datetime.datetime.strptime(toTime, '%Y-%m-%d')
            if showChart:
                self.logger.debug("Showing chart for period {0} - {1} aggregated to {2} for sensors {3}".format(fromTimeParsed, toTimeParsed, aggregation, chartSensors))
                chartData = self.iotManager.database.getChartData(chartSensors, fromTimeParsed, toTimeParsed, aggregation)
                finalChartSensors = []
                for sensor in chartSensors:
                    if not all(sensor.fullId not in record for record in chartData):
                      finalChartSensors.append(sensor)
                chartSensors = finalChartSensors
            self.render("views/history.html", sensors=sensors, fromTime=fromTime, toTime=toTime, aggregation=aggregation, showChart=showChart, chartData=chartData, chartSensors=chartSensors)      
        else:
            self.redirect("/login?"+urllib.urlencode({"returnUrl":self.request.uri}))
            
class LoginWebHandler(BaseWebHandler):
    logger = logging.getLogger()
    
    def initialize(self, adminPasswordHash):
        self.adminPasswordHash = adminPasswordHash    

    def get(self):
        returnUrl = self.get_argument("returnUrl", "/")
        self.render("views/login.html", returnUrl=returnUrl)     
        
    def post(self):
        username = tornado.escape.xhtml_escape(self.get_argument("username", ""))
        password = tornado.escape.xhtml_escape(self.get_argument("password", "")).encode('utf-8')   
        returnUrl = self.get_argument("returnUrl", "/")
        self.logger.info("login request with username={0} from ip={1}".format(username, self.request.remote_ip))
        if username == "admin" and bcrypt.hashpw(password, self.adminPasswordHash) == self.adminPasswordHash:
            self.set_secure_cookie("user", username)
            self.redirect(returnUrl)
        else:
            self.logger.warning("Invalid login/password request with username={0} from ip={1}".format(username, self.request.remote_ip))
            self.render("views/login.html", errormsg="Invalid username or password.", returnUrl=returnUrl)       
        
class LogoutWebHandler(BaseWebHandler):
    def get(self):
        self.clear_cookie("user")
        self.redirect("/") 
        
class WSHandler(tornado.websocket.WebSocketHandler):
    logger = logging.getLogger()
    connections = set()
    
    def initialize(self, service, deviceConfig, iotManager):
        self.service = service
        self.deviceConfig = deviceConfig    
        self.iotManager = iotManager
    
    @staticmethod
    def sendMessageToAll(msg):
        for con in set(WSHandler.connections):
            try:
                con.write_message(msg)
            except:
                pass
    
    def open(self):
        self.logger.debug('WS New connection was opened from {0}'.format(self.request.remote_ip))
        user = self.get_secure_cookie("user")
        if user == "admin":
            self.connections.add(self)
        else:
            self.logger.warning("Unauthorized WS connection fron {0}!".format(self.request.remote_ip))
            self.write_message(json.dumps({'error':123}))
            try:
                self.close()
            except:
                pass
            
    def on_message(self, message):
        self.logger.debug('WS Incoming message:{0} from {1}'.format(message, self.request.remote_ip))
        user = self.get_secure_cookie("user")
        if user == "admin":
            parsed = json.loads(message)
            if "command" in parsed and "deviceId" in parsed:
                cmdConf = self.iotManager.deviceConfig[parsed["deviceId"]]["commands"][parsed["command"]]
                payload = {}
                for attr, val in cmdConf.items():
                    if attr != "label":
                        payload[attr] = val
                payloadStr = json.dumps(payload)
                deviceIdHex = parsed["deviceId"]
                deviceId = str(bytearray.fromhex(deviceIdHex))
                self.logger.info("Sending message {0} to device {1}".format(payloadStr, deviceIdHex))
                self.service.sendMessage(deviceId, payloadStr)
        else:
            try:
                self.close()
            except:
                pass
        
           
    def on_close(self):
        try:
            self.connections.remove(self)
        except:
            pass
        self.logger.debug('WS Connection from {0} was closed.'.format(self.request.remote_ip))        