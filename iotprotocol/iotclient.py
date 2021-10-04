from iotcommon import UdpPacket
from iotcommon import IotUDPHandler
import SocketServer
import iotcommon
import logging.config
import logging
import threading
import sys
import binascii
import os
import socket, ssl
import time
import sys

class IotClientService:
    logger = logging.getLogger()
    IOT_PROTOCOL_VERSION = 1
    
    def __init__(self, protocol, serverAddr, deviceId, deviceKey, deviceHandler):
        self.serverAddr = serverAddr
        self.protocol = protocol
        self.deviceId = deviceId
        self.deviceKey = deviceKey
        self.lock = threading.Lock()
        if self.protocol == "udp":
            self.udpHeartbeatSeconds = 2
            self.udpDataPacketInterval = 3
            self.heartbeatCounter = 0
            self.stateFile = "client.dat"
        elif self.protocol == "ssl":
            self.caCertFile = "servercert.pem"
            self.deviceCertFile = "devicecert.pem"
            self.deviceKeyFile = "devicekey.pem"
            self.sslIntervalSeconds = 6
        self.deviceHandler = deviceHandler
        self.deviceHandler.service = self
        
    def start(self):
        self.deviceHandler.start()
        if self.protocol == "udp":
            self.loadState()        
            self.logger.debug("udpHeartbeatSeconds = {0}".format(self.udpHeartbeatSeconds))
            self.logger.debug("udpDataPacketInterval = {0}".format(self.udpDataPacketInterval))
            self.udpServer = SocketServer.UDPServer(('0.0.0.0', 0), IotUDPHandler)
            self.udpServer.service = self
            self.udpServer.role = IotUDPHandler.CLIENT
            self.logger.info("starting UDP client at {0}:{1} connecting to {2}, state at {3}".format(self.udpServer.server_address[0], self.udpServer.server_address[1], self.serverAddr, self.stateFile))            
            timer = threading.Timer(0.5, self.repeat)
            timer.daemon = True
            timer.start()
            self.udpServer.serve_forever()      
        elif self.protocol == "ssl": 
            while True:
                self.logger.info("Connecting by SSL to server at {0}".format(self.serverAddr))
                try:
                    sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
                    self.logger.debug("using caCertFile={0}, deviceCertFile={1}, deviceKeyFile={2}".format(self.caCertFile, self.deviceCertFile, self.deviceKeyFile))
                    sslSocket = ssl.wrap_socket(sock, ca_certs=self.caCertFile, cert_reqs=ssl.CERT_REQUIRED, certfile=self.deviceCertFile, keyfile=self.deviceKeyFile, ssl_version=ssl.PROTOCOL_SSLv23)     
                    sslSocket.connect((self.serverAddr.split(':')[0], int(self.serverAddr.split(':')[1])))   
                    servercert = sslSocket.getpeercert()
                    subject = dict(x[0] for x in servercert['subject'])
                    self.logger.info("Connected to server with valid certificate, CN={0}".format(subject['commonName']))  
                    sslSocket.settimeout(2*self.sslIntervalSeconds)
                    self.sslSocket = sslSocket
                    sslThread = threading.Thread(target = self.sslListen, args = (self.sslSocket,))
                    sslThread.daemon = True
                    sslThread.start()
                    while True:
                        payload = self.deviceHandler.getMessagePayload()
                        self.logger.debug("Sending payload to {0} by SSL: {1}".format(self.serverAddr, payload))
                        iotcommon.sendMessage(self.sslSocket, payload)
                        time.sleep(self.sslIntervalSeconds)
                except Exception as e: 
                    self.logger.exception(e)
                time.sleep(10)
                
    def sslListen(self, sslSocket):
        try:
            while True:
                payload = iotcommon.recvMessage(sslSocket)
                clientAddr = sslSocket.getpeername()
                self.logger.info("Received SSL payload from server at {0}:{1} : {2}".format(clientAddr[0], clientAddr[1], payload))
                self.passToHandler(payload)
        except Exception as e:                
            self.logger.exception(e)
            sslSocket.close()
            
    def sendMessage(self, payload):
        if self.protocol == "ssl":
            self.sendSsl(payload)
        elif self.protocol == "udp":
           self.sendUdp(payload)
            
    def repeat(self):
        try:
            self.udpHeartbeat()
        except Exception as e: 
            self.logger.exception(e)
        except:   
            self.logger.error("error on executing heartbeat: {0} ".format(sys.exc_info()[0]))           
        timer = threading.Timer(self.udpHeartbeatSeconds, self.repeat)
        timer.daemon = True
        timer.start()
        
    def udpHeartbeat(self):
        if self.heartbeatCounter % self.udpDataPacketInterval == 0:
            payload = self.deviceHandler.getMessagePayload()
            self.sendUdp(payload)
        else:
            data = "IOT\xff"
            host, port = self.serverAddr.split(':')[0], int(self.serverAddr.split(':')[1])
            self.logger.debug("Sending 4 bytes UDP heartbeat to {0}:{1}".format(host, port))
            with self.lock:            
                self.udpServer.socket.sendto(data, (host, port))
        self.heartbeatCounter+=1
            
    def sendUdp(self, payload):
        host, port = self.serverAddr.split(':')[0], int(self.serverAddr.split(':')[1])
        message = UdpPacket(self.deviceId, UdpPacket.CLIENT_TO_SERVER, self.IOT_PROTOCOL_VERSION, self.udpSentCounter, 0, payload)
        data = message.createPacket(self.deviceKey)     
        self.logger.debug("Sending {0} byte(s) by UDP to {1}:{2}: {3}".format(len(data), host, port, payload))
        with self.lock:
            self.udpServer.socket.sendto(data, (host, port))
        self.udpSentCounter+=1
        self.saveState()        
    
    def sendSsl(self, payload):
        self.logger.debug("Sending {0} byte(s) by SSL to {1}: {2}".format(len(payload), self.serverAddr, payload))
        with self.lock:
            iotcommon.sendMessage(self.sslSocket, payload)      
        
    def handleUdpMessage(self, message, remoteAddr):
        self.logger.debug("    handling decoded UDP message from server")
        if str(message.deviceId) == str(self.deviceId):
            self.logger.debug("Validating counters in incoming server message: local={0},{1}, message={2},{3}".format(self.udpSentCounter, self.udpReceivedCounter, message.counter1, message.counter2))
            if (message.counter1 > self.udpReceivedCounter and message.counter2 >= self.udpSentCounter - 5):
                self.udpReceivedCounter = message.counter1
                self.logger.info("Counters OK. Received valid message from server at {0}:{1} with payload {2}".format(remoteAddr[0], remoteAddr[1], message.payload))
                self.saveState()
                self.passToHandler(message.payload)
            else:
                self.logger.warning("Invalid counters in incoming message. local={0},{1}, message={2},{3} - discarding".format(self.udpSentCounter, self.udpReceivedCounter, message.counter1, message.counter2))
        else:
            self.logger.warning("Device key mismatch! local=%s, incoming=%s", binascii.hexlify(self.deviceId), binascii.hexlify(message.deviceId))
    
    def passToHandler(self, payload):
        try:
            self.deviceHandler.handleServerCall(payload)
        except Exception as e: 
            self.logger.exception(e)
    
    def loadState(self):
        if not os.path.exists(self.stateFile):
            self.logger.warning("State file at {0} doesn't exist. Creating initial state file with (1,0)".format(self.stateFile))
            with open(self.stateFile, 'w') as f:
                f.write("1 0")
            self.udpSentCounter = 1
            self.udpReceivedCounter = 0              
        else:
            with open(self.stateFile, 'r') as f:
                line = f.readline()
                self.udpSentCounter = int(line.split(' ')[0])
                self.udpReceivedCounter = int(line.split(' ')[1])
            self.logger.info("State loaded from file {0}: ({1},{2})".format(self.stateFile, self.udpSentCounter, self.udpReceivedCounter))
                
    def saveState(self):
        tmpFile = self.stateFile + ".tmp" #tmp file for atomic write
        with open(tmpFile, 'w') as f:
            f.write(str(self.udpSentCounter) + ' ' + str(self.udpReceivedCounter))
        os.rename(tmpFile, self.stateFile)    
        self.logger.info("State saved to file {0}: ({1},{2})".format(self.stateFile, self.udpSentCounter, self.udpReceivedCounter))
