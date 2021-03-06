import logging
import tornado.web
import os
import binascii
import bcrypt
import json
import datetime
import urllib
import database
import socket
import time
import threading
import tornado.web
from tornado import gen, web, httpclient
from tornado.gen import Return
from models import DeviceModel
from models import SensorValue
from models import UploadedImage
from models import SensorFilter

class RedirectorHandler(tornado.web.RequestHandler):
    def initialize(self, manager):
        self.manager = manager
        
    def get(self):
        host = self.request.host
        host = host.split(':')[0]
        if self.manager.httpsPort != 443:
            host += ":{0}".format(self.manager.httpsPort)
        redirectTo = "https://{0}".format(host)        
        self.redirect(redirectTo)   
             
class BaseWebHandler(tornado.web.RequestHandler):
  def isAuthenticated(self):
    user = self.get_secure_cookie("user", max_age_days=1)
    if user:
        return True
    else:
        return False  
        
        
class AuthFileHandler(BaseWebHandler):   
    logger = logging.getLogger()  

    def initialize(self, path):
        self.path = path   

    def get(self, file):
        if self.isAuthenticated():
            if file.find("..") > -1:
                return
            fullPath = os.path.join(self.path, file)
            if not os.path.exists(fullPath):
                self.set_status(404)
                self.write("404 Not Found")
                return
            ext = file.split('.')[-1]
            contentType = "application/octet-stream"
            if ext == "jpg" or ext== "jpeg" or ext == "bmp":
                contentType = "image/{0}".format(ext) 
            self.logger.debug("serving file {0}".format(fullPath))
            with open(fullPath, mode='rb') as file:
                fileData = file.read()
                self.write(fileData)
                self.set_header("Content-Type", contentType)
        else:       
            self.redirect("/login?"+urllib.urlencode({"returnUrl":self.request.uri}))
        
class VideoWebHandler(BaseWebHandler):		
    logger = logging.getLogger()   
    
    def initialize(self, localVideoPort):
        self.localVideoPort = localVideoPort
        
    def get(self):
        if self.isAuthenticated():
            self.logger.info("Attempting to stream video from 127.0.0.1:{0}".format(self.localVideoPort))
            self.clear()
            self.set_status(200)
            self.set_header('Connection', 'close')
            self.set_header('Max-Age', '0')
            self.set_header('Expires', '0')
            self.set_header('Cache-Control', 'no-cache, private')
            self.set_header('Pragma', 'no-cache')
            self.set_header('Content-type','multipart/x-mixed-replace; boundary=--BoundaryString')
            self.flush()  
            
            self.sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            self.sock.connect(('127.0.0.1', self.localVideoPort))   
            self.sock.sendall("GET http://127.0.0.1:{0}/ HTTP/1.1\r\nHost: 127.0.0.1:{0}\r\n\r\n".format(self.localVideoPort))
            
            #read headers from mjpg stream
            line = self.readLine()
            while len(line) > 0:
                self.logger.debug("header line from video server: {0}".format(line))
                line = self.readLine()
            
            #stream video
            self.logger.info("Starting serving mjpg stream")
            self._auto_finish = False;
            threading.Thread(target = self.streamVideo).start()
        else:
            self.redirect("/login?"+urllib.urlencode({"returnUrl":self.request.uri}))
   
    def streamVideo(self):
        cont = True
        while cont:
            buffer = self.sock.recv(100000)
            if len(buffer) > 0:
                self.logger.debug("received {0} bytes of video stream".format(len(buffer)))
                self.write(buffer)
                self.set_header('Content-type','Content-type: image/jpeg')              
                self.flush()
            else:
                cont = False            
            
    def readLine(self):
        c1 = None
        c2 = None
        line = ""
        while c1 != '\r' and c2 != '\n':
            buf = self.sock.recv(1)
            if len(buf) > 0:
                c1 = c2
                c2 = buf[0]
                line += buf
        return line[:-2]                
        
class HomeWebHandler(BaseWebHandler):
    def initialize(self, iotManager):
        self.iotManager = iotManager

    def get(self):
        if self.isAuthenticated():
            devices = self.iotManager.getOnlineDevices()
            self.render("views/home.html", devices=devices)      
        else:
            self.redirect("/login")
            
class DevicesWebHandler(BaseWebHandler):
    logger = logging.getLogger()
    
    def initialize(self, iotManager):
        self.iotManager = iotManager
        
    def get(self):
        if self.isAuthenticated():          
            devices = self.iotManager.getAllDevices()        
            self.render("views/devices.html", devices=devices)               
        else:
            self.redirect("/login?"+urllib.urlencode({"returnUrl":self.request.uri}))            
            
class RssWebHandler(BaseWebHandler):
    logger = logging.getLogger()
    
    def initialize(self, iotManager):
        self.iotManager = iotManager
        
    def get(self):     
        devices = self.iotManager.getOnlineDevices()
        xml = self.render_string("views/rss.xml", devices=devices)               
        self.set_header('Content-Type', 'text/xml')
        self.finish(xml)
        
class ApiWebHandler(BaseWebHandler):
    logger = logging.getLogger()
    
    def initialize(self, iotManager):
        self.iotManager = iotManager
        
    def get(self):    
        user = user = self.getUser()
        if user == "admin":    
            onlinedevices = self.iotManager.getOnlineDevices()
            dev = [{'id':d.deviceId, 'values':[{'id':v.id, 'value':v.value, 'label':v.label} for v in d.values]} for d in onlinedevices]
            response = { 'devices': dev }       
            self.set_header('Content-Type', 'application/json')
            self.finish(json.dumps(response))      
        else:
            self.logger.warning("Unauthorized API connection from {0}!".format(self.request.remote_ip))
            self.clear()
            self.set_status(403) 
            self.set_header('Content-Type', 'application/json')
            self.finish(json.dumps({'error':123, 'message':'forbiden'}))
            try:
                self.close()
            except:
                pass   
                
    def getUser(self):
        user = self.get_secure_cookie("user", max_age_days=1)
        if user is None:
            secret = self.get_argument("secret", None)
            if secret == self.iotManager.apiSecret:
                user = "admin"
            else:
                self.logger.warning("Invalid secret when calling WS api from {0}".format(self.request.remote_ip))
        return user                
           
class DeviceWebHandler(BaseWebHandler):
    logger = logging.getLogger()
    
    def initialize(self, iotManager):
        self.iotManager = iotManager
        
    def get(self, deviceIdHex):
        if self.isAuthenticated():
            imagesCount = int(tornado.escape.xhtml_escape(self.get_argument("images", "6")))
            deviceModel = self.iotManager.getDevice(deviceIdHex, imagesCount)
            if deviceModel:
                self.render("views/device.html", device = deviceModel, imagesCount=imagesCount)    
            else:
                self.logger.warning("device {0} not found".format(deviceIdHex))            
        else:
            self.redirect("/login?"+urllib.urlencode({"returnUrl":self.request.uri}))

class HistoryWebHandler(BaseWebHandler):
    logger = logging.getLogger()

    def initialize(self, iotManager):
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
            for deviceId, conf in self.iotManager.deviceConfig.items():
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

class LogsWebHandler(BaseWebHandler):
    logger = logging.getLogger()

    def initialize(self, iotManager):
        self.iotManager = iotManager

    def get(self, deviceIdHex):
        self.logger.info("LogsWebHandler 0")  
        if self.isAuthenticated():
            self.logger.info("LogsWebHandler 1")  
            fromTime = tornado.escape.xhtml_escape(self.get_argument("fromTime", (datetime.datetime.now() - datetime.timedelta(days=2)).strftime('%Y-%m-%d')))
            toTime = tornado.escape.xhtml_escape(self.get_argument("toTime", (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')))   
            self.logger.info("LogsWebHandler 2")  
            deviceModel = self.iotManager.getDevice(deviceIdHex, 1)
            fromTimeParsed = datetime.datetime.strptime(fromTime, '%Y-%m-%d')
            toTimeParsed = datetime.datetime.strptime(toTime, '%Y-%m-%d')   
            self.logger.info("LogsWebHandler 3")                
            logData = self.iotManager.database.getLogData(deviceIdHex, fromTimeParsed, toTimeParsed) 
            self.render("views/logs.html", fromTime=fromTime, toTime=toTime, logData=logData, device = deviceModel)               
            
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
            self.set_secure_cookie("user", username, expires_days=1)
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
    
    def initialize(self, iotManager): 
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
        user = self.getUser()
        if user == "admin":
            self.connections.add(self)
        else:
            self.logger.warning("Unauthorized WS connection from {0}!".format(self.request.remote_ip))
            self.write_message(json.dumps({'error':123}))
            try:
                self.close()
            except:
                pass
            
    def on_message(self, message):
        self.logger.debug('WS Incoming message:{0} from {1}'.format(message, self.request.remote_ip))
        user = user = self.getUser()
        if user == "admin":
            parsed = json.loads(message)
            if "command" in parsed and "deviceId" in parsed:
                self.iotManager.sendCommand(parsed["deviceId"], parsed["command"])
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
        
    def check_origin(self, origin):
        self.logger.debug('WS connection origin check: {0}'.format(origin))
        return True        

    def getUser(self):
        user = self.get_secure_cookie("user", max_age_days=1)
        if user is None:
            secret = self.get_argument("secret", None)
            if secret == self.iotManager.apiSecret:
                user = "admin"
            else:
                self.logger.warning("Invalid secret when calling WS api from {0}".format(self.request.remote_ip))
        return user
    