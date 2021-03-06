from iotprotocol.iotclient import IotClientService
from iotprotocol.iotcommon import getFullPath
from iotprotocol.iotcommon import configureLogging
from iotprotocol.daemon import Daemon
import logging
import ConfigParser
import os
import argparse
import importlib
import time
from Tkinter import *
import Tkinter as tk
import threading
import datetime
import random
import locale
import subprocess
import binascii
import sys, os, time, atexit
from signal import SIGTERM
import websocket
import json
        
class IotWindow:
    logger = logging.getLogger()

    def __init__(self, screenName, width, height):
        self.screenName = screenName
        self.root = None
        self.canvas = None
        self.rectSensor1 = None
        self.rectSensor2 = None
        self.rectTime = None
        self.txtSensor1 = None
        self.txtSensor2 = None
        self.txtTime = None
        self.txtSensor11Desc = None
        self.txtSensor2Desc = None
        self.thread = None
        self.txtSensor1SmallIcon = None
        self.txtSensor2SmallIcon = None
        self.txtSensor1BigIcon = None
        self.txtSensor2BigIcon = None
        self.sensor1ts = datetime.datetime.now()
        self.sensor2ts = datetime.datetime.now()
        self.expirationSeconds = 120
        self.width = width
        self.height = height
        
    def start(self):
        self.root = None
        while not self.root:
            try:
                self.root = Tk(screenName=self.screenName)
            except:
                time.sleep(1)
        self.root.attributes("-fullscreen",True)
        self.root.config(cursor='none')
        self.canvas = Canvas(self.root, width = self.width, height=self.height, bg="black")
        self.canvas.pack()
        #img=PhotoImage(file="/home/pi/test.gif")
        #canvas.create_image(240, 160, image=img) 
        self.rectSensor1 = self.canvas.create_rectangle(0, 0, int(self.width / 1.5), int(self.height * 0.46875), fill="black", outline="white")
        self.rectSensor2 = self.canvas.create_rectangle(0, int(self.height * 0.46875), int(self.width / 1.5), int(self.height * 0.75), fill="black", outline="white")
        self.rectTime = self.canvas.create_rectangle(0, int(self.height * 0.75), self.width, self.height, fill="black", outline="white")
        self.txtSensor1 = self.canvas.create_text(int(self.width / 3), int(self.height * 0.265625), text="", font=('Helvetica Neue UltraLight', int(self.height * 0.2)), fill="white", anchor='c', tag='sensor1') 
        self.txtSensor1BigIcon = self.canvas.create_text(int(self.width * 0.835),int(self.height * 0.265625),text="",font=('Helvetica Neue UltraLight',int(self.height * 0.3)), fill="white",anchor='c',tag='sensor1bi')
        self.txtSensor2 = self.canvas.create_text(int(self.width / 3), int(self.height * 0.640625), text="", font=('Helvetica Neue UltraLight', int(self.height*0.11875)),fill="white", anchor='c', tag='sensor2')    
        self.txtSensor2BigIcon = self.canvas.create_text(int(self.width * 0.835),int(self.height * 0.640625),text="",font=('Helvetica Neue UltraLight',int(self.height*0.18)),fill="white",anchor='c',tag='sensor2bi')
        self.txtTime = self.canvas.create_text(int(self.width / 2), int(self.height * 0.875), text="", font=('Helvetica Neue UltraLight', int(self.height * 0.125)), fill="white", anchor='c', tag='time') 
        self.txtSensor1Desc = self.canvas.create_text(int(self.width / 3), int(self.height * 0.046875), text="", font=('Helvetica Neue UltraLight', int(self.height * 0.05)), fill="white", anchor='c', tag='sensor1desc')
        self.txtSensor1SmallIcon = self.canvas.create_text(int(self.width * 0.635), int(self.height * 0.046875),text="", font=('Helvetica Neue UltraLight', int(self.height * 0.05)), fill="white",anchor='c',tag='sensor1si')
        self.txtSensor2Desc = self.canvas.create_text(int(self.width / 3), int(self.height * 0.515625), text="", font=('Helvetica Neue UltraLight', int(self.height * 0.05)), fill="white", anchor='c', tag='sensor2desc')
        self.txtSensor2SmallIcon = self.canvas.create_text(int(self.width * 0.635), int(self.height * 0.515625),text="", font=('Helvetica Neue UltraLight', int(self.height * 0.05)), fill="white",anchor='c',tag='sensor2si')
        #for i in range(-154, 154):
        #    t = i * 0.25
        #    r = self.canvas.create_rectangle(160+t*4, 1, 160+t*4+1, 5, fill=self.mapColor(t), outline=self.mapColor(t))       
        self.thread = threading.Thread(target = self.repeat)
        self.thread.daemon = True
        self.thread.start() 
        self.logger.info("GUI window created, entering main loop")
        self.root.mainloop()        
        
    def displayTime(self):
        self.canvas.itemconfigure(self.txtTime, text=datetime.datetime.now().strftime('%d %b %H:%M:%S'))
        
    def displaySensor1(self,number, description, trend):
        self.canvas.itemconfigure(self.txtSensor1, text="{0:.1f}".format(number)+u'\u2103')
        self.sensor1ts = datetime.datetime.now()
        color = self.mapColor(number)
        if description is not None:
            self.canvas.itemconfigure(self.txtSensor1Desc, text=description)
        self.canvas.itemconfigure(self.txtSensor1, fill=color)
        self.canvas.itemconfigure(self.txtSensor1BigIcon, fill=color) 
        self.canvas.itemconfigure(self.txtSensor1SmallIcon, text=u'\u2022')    
        def hide():
            time.sleep(0.5)
            self.canvas.itemconfigure(self.txtSensor1SmallIcon, text="")
        threading.Thread(target = hide).start()      
        if trend == -1:
            self.canvas.itemconfigure(self.txtSensor1BigIcon, text=u'\u2198') 
        elif trend == 1:
            self.canvas.itemconfigure(self.txtSensor1BigIcon, text=u'\u2197') 
        else:
            self.canvas.itemconfigure(self.txtSensor1BigIcon, text="")
                
        
    def displaySensor2(self,number, description, trend):
        self.canvas.itemconfigure(self.txtSensor2, text="{0:.1f}".format(number)+u'\u2103')  
        self.sensor2ts = datetime.datetime.now()  
        color = self.mapColor(number)        
        if description is not None:
            self.canvas.itemconfigure(self.txtSensor2Desc, text=description)     
        self.canvas.itemconfigure(self.txtSensor2, fill=color)  
        self.canvas.itemconfigure(self.txtSensor2BigIcon, fill=color)  
        self.canvas.itemconfigure(self.txtSensor2SmallIcon, text=u'\u2022')      
        def hide():
            time.sleep(0.5)
            self.canvas.itemconfigure(self.txtSensor2SmallIcon, text="")
        threading.Thread(target = hide).start()            
        if trend == -1:
            self.canvas.itemconfigure(self.txtSensor2BigIcon, text=u'\u2198') 
        elif trend == 1:
            self.canvas.itemconfigure(self.txtSensor2BigIcon, text=u'\u2197') 
        else:
            self.canvas.itemconfigure(self.txtSensor2BigIcon, text="")
            
    def mapColor(self, t):
        r,g,b = 255,255,255
        if t <= -30:
            r,g,b = 128,128,255   # below -30: dark blue
        elif t <= -10:
            r,g,b = self.linearMap(t, -30, -10, 128, 192),self.linearMap(t, -30, -10, 128, 192),255   # -30 to -10: to light blue
        elif t <= 5:
            r,g,b = self.linearMap(t, -10, 5, 192, 0),self.linearMap(t, -10, 5, 192, 255),self.linearMap(t, -10, 5, 255, 192)   # -10 to 5: to aquamarin
        elif t <= 15:
            r,g,b = self.linearMap(t, 5, 15, 0, 128),255,self.linearMap(t, 5, 15, 192, 128)   # 5 to 15: to green
        elif t <= 25:
            r,g,b = self.linearMap(t, 15, 25, 128, 255),255,128   # 15 to 25: to yellow 
        elif t <= 35:
            r,g,b = 255,self.linearMap(t, 25, 35, 255, 128),128   # 25 to 35: to red
        else:
            r,g,b = 255,128,128   # above 30: red   
        return "#" + binascii.hexlify(bytearray([r,g,b]))
        
    def linearMap(self, x, minx, maxx, miny, maxy):
        if x <= minx:
            return int(miny)
        elif x >= maxx:
            return int(maxy)
        else:
            return int(miny + (maxy - miny) * (x - minx) / (maxx - minx))
        
    def repeat(self):
        while True:
            try:
                self.displayTime()
                if (datetime.datetime.now() - self.sensor1ts).total_seconds() > self.expirationSeconds:
                    self.canvas.itemconfigure(self.txtSensor1, text="")
                    self.canvas.itemconfigure(self.txtSensor1BigIcon, text="")
                if (datetime.datetime.now() - self.sensor2ts).total_seconds() > self.expirationSeconds:
                    self.canvas.itemconfigure(self.txtSensor2, text="")      
                    self.canvas.itemconfigure(self.txtSensor2BigIcon, text="")                    
                
                #t = random.random()*60-20
                #self.displaySensor1(t, "test")
            except Exception as e:    
                self.logger.exception(e)
            except:
                pass
            time.sleep(1)  

class WebsocketController:
    logger = logging.getLogger()

    def __init__(self, window, apiAddr, s1, s2):
        self.apiAddr = apiAddr
        self.window = window
        self.ws = None
        self.windowThread = None
        self.device1 = s1.split('.')[0]
        self.sensor1 = s1.split('.')[1]
        self.device2 = s2.split('.')[0]
        self.sensor2 = s2.split('.')[1]
        
    def start(self):
        self.windowThread = threading.Thread(target = self.window.start)
        self.windowThread.daemon = True
        self.windowThread.start() 
        while True:
            try:
                self.ws = websocket.WebSocketApp(self.apiAddr,on_message = self.on_message,on_error = self.on_error,on_close = self.on_close)
                self.ws.on_open = self.on_open
                self.ws.run_forever()
            except:
                self.logger.error("websocket connection error, reconnecting...")
            time.sleep(10)      
                            
    def on_message(self, ws, message):
        self.logger.debug("message received: {0}".format(message))
        parsed = json.loads(message)     
        values = parsed.get("values", None)
        if values is not None:
            deviceId = parsed.get("deviceId", None)
            if deviceId == self.device1:
                sensor = next(v for v in values if v.get("id", None) == self.sensor1)
                if sensor is not None:
                    self.logger.debug("showing value for sensor1: {0}".format(sensor["value"]))
                    self.window.displaySensor1(sensor["value"], parsed["name"]+" "+sensor["label"], sensor.get("trend", None))
            if deviceId == self.device2:
                sensor = next(v for v in values if v.get("id", None) == self.sensor2)
                if sensor is not None:
                    self.logger.debug("showing value for sensor2: {0}".format(sensor["value"]))
                    self.window.displaySensor2(sensor["value"], parsed["name"]+" "+sensor["label"], sensor.get("trend", None))

    def on_error(self, ws, error):
        self.logger.error("WS error")

    def on_close(self, ws):
        self.logger.info("WebSocket closed")

    def on_open(self, ws):
        self.logger.info("WebSocket opened")     
            
if __name__ == "__main__":
    confFile = getFullPath('conf/display.conf')    
    parser = argparse.ArgumentParser(description='IoT GUI display application')    
    parser.add_argument('-c', type=str, dest='config_file', help='display config file', default=confFile)         
    parser.add_argument('command', type=str, help='[start] ,[stop] or [restart] the display as daemon or [run] the display in cosole mode', default='start', choices = ['start', 'stop', 'restart', 'run'])        
    args = parser.parse_args()     
    confFile = getFullPath(args.config_file)
    if not os.path.exists(confFile):
        print('Missing config file at {0}'.format(confFile))
        exit()    
    print('using config at {0}'.format(confFile))
    config = ConfigParser.ConfigParser()
    config.read(confFile)  
    logLevel = logging.getLevelName(config.get('log', 'logLevel'))
    logFile = config.get('log', 'logFile')
    if logFile:
        logFile = getFullPath(logFile)
    configureLogging(logLevel, config.get('log', 'logToConsole'), logFile)
    logger = logging.getLogger()        
    screen = config.get('display', 'screen')
    width = int(config.get('display', 'width'))
    height = int(config.get('display', 'height'))
    apiAddr = config.get('display', 'apiAddr')
    apiSecret = config.get('display', 'apiSecret')
    sensor1 = config.get('display', 'sensor1')
    sensor2 = config.get('display', 'sensor2')
    logger.info("Creating window at screen {0}".format(screen))
    window = IotWindow(screen, width, height)
    logger.info("Connecting to WebSocket API at {0} listening for sensors {1},{2}".format(apiAddr, sensor1, sensor2))
    ws = WebsocketController(window, apiAddr+"?secret="+apiSecret, "3e797b8e7aee511cdb4ecd5063e96b11.t1", "3e797b8e7aee511cdb4ecd5063e96b11.t2")   
    pidFile = config.get('display', 'pidFile')
    daemon = Daemon(pidFile, ws.start, '/dev/null', '/dev/null', '/dev/null')
    if args.command == 'start':
        logger.info("Running display as daemon")
        daemon.start()
    elif args.command == 'stop':
        logger.info("stopping display daemon")
        daemon.stop()
    elif args.command == 'restart':
        logger.info("restarting display daemon")
        daemon.restart()
    elif args.command == 'run':
        logger.info("Running display in console mode")
        ws.start()
    else:
        print "Unknown command"
        sys.exit(2)
