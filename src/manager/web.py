import binascii
import tornado.httpserver
import tornado.websocket
import tornado.ioloop
import tornado.web
import threading
import os
import logging
import database
import handlers
from models import DeviceModel
from models import SensorValue
from models import UploadedImage
from models import SensorFilter

class WebServer:
    logger = logging.getLogger()
    
    def __init__(self, service, deviceConfig, iotManager, port, uploadDir, adminPasswordHash):
        self.service = service
        self.deviceConfig = deviceConfig
        self.iotManager = iotManager
        self.port = port
        self.uploadDir = uploadDir
        self.adminPasswordHash = adminPasswordHash
        self.app = None
        
    def start(self):
        self.logger.info("starting web server listening at port {0} with SSL certificate at {1}".format(self.port, self.iotManager.service.serverCertFile))
        dir = os.path.dirname(os.path.realpath(__file__))
        handlersArgs = dict(service=self.service, deviceConfig=self.deviceConfig, iotManager=self.iotManager)
        
        application = [
        (r'/(favicon.ico)', tornado.web.StaticFileHandler, {'path': dir + '/img'}),
        (r'/static/(.*)', tornado.web.StaticFileHandler, {'path': dir + '/static'}),
        (r'/upload/(.*)', tornado.web.StaticFileHandler, {'path': self.uploadDir}),
        (r'/img/(.*)', tornado.web.StaticFileHandler, {'path': dir + '/img'}),
        (r'/login', handlers.LoginWebHandler, dict(adminPasswordHash=self.adminPasswordHash)),
        (r'/logout', handlers.LogoutWebHandler),
        (r'/ws', handlers.WSHandler, handlersArgs),
        (r'/device/(.*)', handlers.DeviceWebHandler, handlersArgs),
        (r'/history', handlers.HistoryWebHandler, handlersArgs),
        (r'/devices', handlers.DevicesWebHandler, handlersArgs),
        (r'/', handlers.HomeWebHandler, handlersArgs),
        ]
        
        self.app = tornado.web.Application(application, cookie_secret=os.urandom(32), compiled_template_cache=True)
        self.httpServer = tornado.httpserver.HTTPServer(self.app, ssl_options={ "certfile": self.iotManager.service.serverCertFile, "keyfile": self.iotManager.service.serverKeyFile })
        self.httpServer.listen(self.port)
        tornado.ioloop.IOLoop.current().start()    
        
    def websocketSend(self, payload):
        handlers.WSHandler.sendMessageToAll(payload)