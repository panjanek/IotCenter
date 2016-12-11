from iotcommon import IotUDPHandler
from iotcommon import UdpPacket
import datetime
import iotcommon
import SocketServer
import binascii
import logging
import time
import threading
import os
import socket
import ssl
import sys

class IotSession:
    TYPE_UDP = 'udp'
    TYPE_SSL = 'ssl'
    def __init__(self, deviceId, protocol):
        self.protocol = protocol
        self.deviceId = deviceId;
        self.clientAddr = None
        self.lastUdpMessage = None
        self.lastPayload = None
        self.sslSocket = None
        self.creationTime = datetime.datetime.now()
        self.lastUpdateTime = datetime.datetime.now()     
        self.lock = threading.Lock()

class UdpCounter:
    def __init__(self, deviceId, udpSentCounter, udpReceivedCounter):
        self.deviceId = deviceId;
        self.udpSentCounter = udpSentCounter
        self.udpReceivedCounter = udpReceivedCounter
        
class IotServerService:
    logger = logging.getLogger()
    IOT_PROTOCOL_VERSION = 1
    
    def __init__(self, udpListenAddr, sslListenAddr, masterKey, serverHandler):
        self.udpHost, self.udpPort = udpListenAddr.split(':')[0], int(udpListenAddr.split(':')[1])
        self.sslHost, self.sslPort = sslListenAddr.split(':')[0], int(sslListenAddr.split(':')[1])
        self.udpServer = None
        self.udpTimeout = 180
        self.sessions = dict()
        self.masterKey = masterKey
        self.stateFile = 'server.dat'
        self.caCertFile = 'servercert.pem'
        self.serverCertFile = 'servercert.pem'
        self.serverKeyFile = 'serverkey.pem'
        self.taskIntervalSecond = 60        
        self.serverHandler = serverHandler
        self.serverHandler.service = self
        
    def start(self):
        self.loadState()   
        self.serverHandler.start()
        sslThread = threading.Thread(target = self.startSsl)
        sslThread.daemon = True
        sslThread.start()
        timer = threading.Timer(self.taskIntervalSecond, self.repeat)
        timer.daemon = True
        timer.start()       
        self.udpServer = SocketServer.UDPServer((self.udpHost, self.udpPort), IotUDPHandler)
        self.logger.info("starting UDP server listening at {0}:{1}".format(self.udpServer.server_address[0], self.udpServer.server_address[1]))
        self.udpServer.service = self
        self.udpServer.role = IotUDPHandler.SERVER        
        self.udpServer.serve_forever()  
        
    def startSsl(self):
        while True:
            try:
                self.logger.info("starting TCP SSL server listening at {0}:{1}".format(self.sslHost, self.sslPort))
                bindsocket = socket.socket()
                bindsocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  #bind even if local port is in TIME_WAIT
                bindsocket.bind((self.sslHost, self.sslPort))
                bindsocket.listen(5)
                while True:
                    newsocket, fromaddr = bindsocket.accept()
                    try:
                        self.logger.info("New TCP connection from {0}:{1} - initiating ssl using serverCertFile={2}, serverKeyFile={3}, caCertFile={4}".format(fromaddr[0], fromaddr[1], self.serverCertFile, self.serverKeyFile, self.caCertFile))
                        sslSocket = ssl.wrap_socket(newsocket, server_side=True,certfile=self.serverCertFile, keyfile=self.serverKeyFile,cert_reqs=ssl.CERT_REQUIRED,ca_certs=self.caCertFile,ssl_version=ssl.PROTOCOL_TLSv1)
                        servercert = sslSocket.getpeercert()
                        subject = dict(x[0] for x in servercert['subject'])
                        cn = subject['commonName']
                        desc = subject['description']
                        self.logger.info("Client certificate is valid, CN={0}, description={1} - validating deviceId and description".format(cn, desc))
                        deviceId = str(bytearray.fromhex(cn))
                        deviceKey = iotcommon.deriveKey(self.masterKey, deviceId)
                        expectedSignature = binascii.hexlify(iotcommon.hmacsha256(deviceId, deviceKey))
                        if desc == expectedSignature:
                            self.logger.debug("certificate signature OK, creating session for device {0} at {1}:{2}".format(cn, fromaddr[0], fromaddr[1]))
                            if deviceId in self.sessions:
                                session = self.sessions[deviceId]       
                                session.clientAddr = fromaddr
                                session.sslSocket = sslSocket
                                session.lastUpdateTime = datetime.datetime.now()                                  
                            else:
                                self.logger.debug("    creating new session for SSL device: %s", binascii.hexlify(deviceId))
                                session = IotSession(deviceId, IotSession.TYPE_SSL)
                                session.clientAddr = fromaddr
                                session.sslSocket = sslSocket
                                session.lastUpdateTime = datetime.datetime.now()                                
                                self.sessions[deviceId] = session               
                            self.logger.debug("Creating thread for handling SSL communication with {0}".format(binascii.hexlify(deviceId)))
                            conectionThread = threading.Thread(target = self.hadleSslCommunication, args = (deviceId, sslSocket))
                            conectionThread.daemon = True
                            conectionThread.start()
                        else:
                            sslSocket.shutdown(socket.SHUT_RDWR)
                            sslSocket.close()
                            self.logger.warning('received invalid signature in certificate description field for device {0}. expected={1}, received={2} - closing connection'.format(cn, binascii.hexlify(expectedSignature), desc))
                    except Exception as e:
                        self.logger.exception(e)
                        try:
                            newsocket.shutdown(socket.SHUT_RDWR)
                            newsocket.close()
                        except:
                            pass
            except Exception as e:
                self.logger.exception(e)
                time.sleep(10)
        
    def hadleSslCommunication(self, deviceId, sslSocket):
        try:
            while True:
                payload = iotcommon.recvMessage(sslSocket)
                clientAddr = sslSocket.getpeername()
                self.logger.debug("Received SSL payload from {0} at {1}:{2}: {3}".format(binascii.hexlify(deviceId), clientAddr[0], clientAddr[1], payload))
                if deviceId in self.sessions:
                    session = self.sessions[deviceId]               
                else:
                    self.logger.debug("    creating new session for SSL device: %s", binascii.hexlify(deviceId))
                    session = IotSession(deviceId, IotSession.TYPE_SSL)
                    self.sessions[deviceId] = session                 
                session.lastUpdateTime = datetime.datetime.now()
                session.lastPayload = payload
                if self.logger.getEffectiveLevel() == logging.DEBUG:
                    self.dumpSessions()                        
                self.passToHandler(deviceId, payload)
        except Exception as e:
            self.logger.exception(e)
            try:
                self.removeSession(deviceId)
                sslSocket.shutdown(socket.SHUT_RDWR)
                sslSocket.close()
            except:
                pass                
        
    def repeat(self):
        try:
            self.task()
        except Exception as e: 
            self.logger.exception(e)
        except:   
            self.logger.error("error on executing task: {0} ".format(sys.exc_info()[0]))           
        timer = threading.Timer(self.taskIntervalSecond, self.repeat)
        timer.daemon = True
        timer.start()   

    def task(self):
        self.saveState()   
        self.removeInactiveSessions()          
              
    def handleUdpMessage(self, message, clientAddr):
        self.logger.debug("    handling decoded UDP message from device")
        isNewSession = False
        if message.deviceId in self.sessions:
            session = self.sessions[message.deviceId]               
        else:
            self.logger.debug("    attemping to create new session for UDP device: %s", binascii.hexlify(message.deviceId))
            session = IotSession(message.deviceId, IotSession.TYPE_UDP)
            isNewSession = True
        
        counter = self.getCounter(message.deviceId)
        self.logger.debug("    Validating counters: local={0}, incoming={1}".format(counter.udpReceivedCounter, message.counter1))    
        if (message.counter1 > counter.udpReceivedCounter):         
            self.logger.debug("    Counter OK. updating session for device %s", binascii.hexlify(message.deviceId))    
            session.lastUdpMessage = message
            session.lastPayload = message.payload
            session.clientAddr = clientAddr                        
            session.lastUpdateTime = datetime.datetime.now()
            counter.udpReceivedCounter = message.counter1            
            if isNewSession:
                self.sessions[message.deviceId] = session                    
            self.logger.info("Received valid UDP message from {0}:{1}, deviceId={2}, payload={3}. Calling server handler.".format(clientAddr[0], clientAddr[1], binascii.hexlify(message.deviceId), message.payload))
            self.passToHandler(message.deviceId, message.payload)
        else:
            self.logger.warning("Invalid counter in message from device {0}, local={1}, incoming={2} - discarding".format(binascii.hexlify(message.deviceId), counter.udpReceivedCounter, message.counter1))        
                    
    def sendMessage(self, deviceId, payload):
        self.logger.debug("Attempting do send message to device %s, payload %s", binascii.hexlify(deviceId), payload)
        if deviceId in self.sessions:
            session = self.sessions[deviceId]            
            if session.protocol == IotSession.TYPE_UDP:
                counter = self.getCounter(deviceId)
                message = UdpPacket(deviceId, UdpPacket.SERVER_TO_CLIENT, self.IOT_PROTOCOL_VERSION, counter.udpSentCounter, session.lastUdpMessage.counter1, payload)    
                deviceKey = iotcommon.deriveKey(self.masterKey, deviceId)
                data = message.createPacket(deviceKey)
                self.logger.info("Sending {0} bytes in UDP to device {1} at {2}:{3}".format(len(data), binascii.hexlify(message.deviceId), session.clientAddr[0], session.clientAddr[1]))
                with session.lock:
                    self.udpServer.socket.sendto(data, session.clientAddr)
                counter.udpSentCounter += 1
                self.saveState()
            elif session.protocol == IotSession.TYPE_SSL:
                self.logger.info("Sending {0} bytes by SSL to device {1} at {2}:{3}".format(len(payload), binascii.hexlify(deviceId), session.clientAddr[0], session.clientAddr[1]))
                with session.lock:
                    iotcommon.sendMessage(session.sslSocket, payload)
        else:
            self.logger.warning("could not send message to device - device %s is not connected", binascii.hexlify(message.deviceId))
            return False
            
    def passToHandler(self, deviceId, payload):            
        try:
            self.serverHandler.handleDeviceCall(deviceId, payload)        
        except Exception as e:
            self.logger.exception(e)
            
    def removeInactiveSessions(self):
        for deviceId, session in self.sessions.items():
            secs = (datetime.datetime.now() - session.lastUpdateTime).total_seconds()
            if session.protocol == "udp" and secs > self.udpTimeout:
                self.logger.info("UDP session for device {0} at {1}:{2} is inactive for {3} - removing".format(binascii.hexlify(deviceId), session.clientAddr[0], session.clientAddr[1], secs))
                self.removeSession(deviceId)
            
    def loadState(self):
        self.counters =  dict()      
        if not os.path.exists(self.stateFile):
            self.logger.warning("State file at {0} doesn't exist. Creating initial empty counters file.".format(self.stateFile))
            f = open(self.stateFile, 'w')
            f.close()
                     
        else:
            with open(self.stateFile, 'r') as f:
                lines = f.readlines()
                for line in lines:
                    split = line.split(' ')
                    deviceId = str(bytearray.fromhex(split[0]))
                    sentCounter = int(split[1])
                    receivedCounter = int(split[2])
                    self.counters[deviceId] = UdpCounter(deviceId, sentCounter, receivedCounter)
            self.logger.info("{0} record(s) loaded from state file at {1}".format(len(self.counters), self.stateFile))
            
    def saveState(self):
        tmpFile = self.stateFile + '.tmp'
        with open(tmpFile, 'w') as f:
            for deviceId, counter in self.counters.items():
                f.write(binascii.hexlify(deviceId) + ' ' + str(counter.udpSentCounter) + ' ' + str(counter .udpReceivedCounter) + '\n')
        os.rename(tmpFile, self.stateFile)  
        self.logger.info("{0} counter(s) saved to file {1}".format(len(self.counters), self.stateFile))    

    def getCounter(self, deviceId):
        if not deviceId in self.counters:
            self.counters[deviceId] = UdpCounter(deviceId, 1, 0)
        return self.counters[deviceId]
        
    def removeSession(self, deviceId):
        try:
            sessions = dict(self.sessions)
            del sessions[deviceId]
            self.sessions = sessions
        except:
            pass            
            
    def dumpSessions(self):
        self.logger.debug("currently %d device(s) connected:", len(self.sessions))
        for deviceId, session in self.sessions.items():
            self.logger.debug("    %s:device %s last updated from %s:%s at %s", session.protocol, binascii.hexlify(deviceId), session.clientAddr[0], session.clientAddr[1], session.lastUpdateTime.strftime('%Y-%m-%d %H:%M:%S'))