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
import ssl

class WebServer:
    logger = logging.getLogger()
    
    def __init__(self, service, deviceConfig, iotManager, httpsPort, httpPort, uploadDir, adminPasswordHash, httpsCertFile, httpsKeyFile, httpsChainFile, localVideoPort):
        self.service = service
        self.deviceConfig = deviceConfig
        self.iotManager = iotManager
        self.httpsPort = httpsPort
        self.httpPort = httpPort
        self.uploadDir = uploadDir
        self.adminPasswordHash = adminPasswordHash
        self.httpsCertFile = httpsCertFile
        self.httpsKeyFile = httpsKeyFile
        self.httpsChainFile = httpsChainFile
        self.localVideoPort = localVideoPort
        self.httpsApp = None
        
    def start(self):
        self.logger.info("starting web server listening at https port {0}".format(self.httpsPort))
        dir = os.path.dirname(os.path.realpath(__file__))
        handlersArgs = dict(service=self.service, deviceConfig=self.deviceConfig, iotManager=self.iotManager)
        
        application = [
        (r'/(favicon.ico)', tornado.web.StaticFileHandler, {'path': dir + '/img'}),
        (r'/static/(.*)', tornado.web.StaticFileHandler, {'path': dir + '/static'}),
        #(r'/upload/(.*)', tornado.web.StaticFileHandler, {'path': self.uploadDir}),
        (r'/upload/(.*)', handlers.AuthFileHandler, {'path': self.uploadDir}),
        (r'/img/(.*)', tornado.web.StaticFileHandler, {'path': dir + '/img'}),
        (r'/login', handlers.LoginWebHandler, dict(adminPasswordHash=self.adminPasswordHash)),
        (r'/logout', handlers.LogoutWebHandler),
        (r'/ws', handlers.WSHandler, handlersArgs),
        (r'/device/(.*)', handlers.DeviceWebHandler, handlersArgs),
        (r'/history', handlers.HistoryWebHandler, handlersArgs),
        (r'/devices', handlers.DevicesWebHandler, handlersArgs),
        (r'/video', handlers.VideoWebHandler, dict(localVideoPort=self.localVideoPort)),
        (r'/', handlers.HomeWebHandler, handlersArgs),
        ]
        
        self.logger.info("starting web server listening at http {0} (plain)".format(self.httpPort))
        self.httpsApp = tornado.web.Application(application, cookie_secret=os.urandom(32), compiled_template_cache=True)
        sslOptions={ "certfile": self.httpsCertFile, "keyfile": self.httpsKeyFile, "ssl_version": ssl.PROTOCOL_TLSv1 }
        if self.httpsChainFile:
            sslOptions["certfile"] = self.httpsChainFile
        self.logger.info("Using certificate file at {0}".format(sslOptions["certfile"]))
        self.httpsServer = tornado.httpserver.HTTPServer(self.httpsApp, ssl_options=sslOptions)
        self.httpsServer.listen(self.httpsPort)
        
        httpApplication = [
            (r'/', handlers.RedirectorHandler, dict(manager = self)),
            (r'/(.*)', tornado.web.StaticFileHandler, {'path': dir + '/plain' })
        ]

        self.httpApp = tornado.web.Application(httpApplication)
        self.httpServer = tornado.httpserver.HTTPServer(self.httpApp)
        self.httpServer.listen(self.httpPort)        
        
        tornado.ioloop.IOLoop.current().start()    
        
    def websocketSend(self, payload):
        handlers.WSHandler.sendMessageToAll(payload)