from Crypto.Cipher import AES
import hashlib
import hmac
import SocketServer
import logging
import logging.config
import binascii
import struct
import socket
import os
import sys

class IotUDPHandler(SocketServer.BaseRequestHandler):
    SERVER = 1
    CLIENT = 2
    logger = logging.getLogger()
    def handle(self):
        try:
            data = self.request[0]
            clientAddr = self.client_address;
            self.logger.debug("UDP packet from {0}:{1}, length {2}".format(clientAddr[0], clientAddr[1], len(data)))
            self.logger.debug("message hex   : %s", binascii.hexlify(data))
            if data[0:4] == "IOT\xff":    
                self.logger.debug("heartbeat packet - ignoring")      
            elif data[0:4] == "IOT\0" and len(data)>=88 and ((len(data)-72)%16) == 0:    
                self.handleIotPacket(data, clientAddr)        
            else:
                self.logger.warning("unknown packet - ignoring")      
        except Exception as e: 
            self.logger.exception(e)
        except:   
            self.logger.error("error on handling incomming packet: {0} ".format(sys.exc_info()[0]))                    

    def handleIotPacket(self, data, clientAddr):    
        hmac = data[4:36]
        type = ord(data[36])
        version = ord(data[37])
        deviceid = data[40:56]
        iv = data[56:72]        
        encryptedBytes = data[72:]
        counter1 = struct.unpack("<Q", data[56:64])[0]
        counter2 = struct.unpack("<Q", data[64:72])[0]        
        if self.logger.getEffectiveLevel() == logging.DEBUG:
            self.logger.debug("received IOT packet")
            self.logger.debug("    type     : %d", type)
            self.logger.debug("    deviceid : %s", binascii.hexlify(deviceid))      
            self.logger.debug("    counter1 : %s", counter1)
            self.logger.debug("    counter2 : %s", counter2)            
            self.logger.debug("    version  : %d", version)
            self.logger.debug("    iv       : %s", binascii.hexlify(iv))
            self.logger.debug("    hmac     : %s", binascii.hexlify(hmac))
            self.logger.debug("    encrypted: %s", binascii.hexlify(encryptedBytes))
        
        #obtain or derive key
        if self.server.role == self.SERVER:
            key = deriveKey(self.server.service.masterKey, deviceid)
        else:
            key = self.server.service.deviceKey           
        self.logger.debug("    key      : %s", binascii.hexlify(key))
        
        #validate signature
        signatureFeed = data[36:]
        expectedHmac = hmacsha256(signatureFeed, key)
        if hmac == expectedHmac:
            self.logger.debug("signature ok")
            
            #decrypt
            decryptedBytes = decrypt(encryptedBytes, key, iv)
            self.logger.debug("    decrypted  : %s", binascii.hexlify(decryptedBytes))
            
            #handle payload
            message = UdpPacket(deviceid, type, version, counter1, counter2, decryptedBytes)
            self.server.service.handleUdpMessage(message, clientAddr)
        else:
            self.logger.warning("Invalid signature in message from {0}:{1}, deviceId={2}: expected={3}, received={4} - discarding".format(clientAddr[0], clientAddr[1], binascii.hexlify(deviceid), binascii.hexlify(expectedHmac),binascii.hexlify(hmac)))
            
class UdpPacket:
    CLIENT_TO_SERVER = 1
    SERVER_TO_CLIENT = 2
    def __init__(self, deviceId, type, version, counter1, counter2, payload):
        self.deviceId = deviceId;
        self.type = type;
        self.version = version;
        self.counter1 = counter1;
        self.counter2 = counter2;
        self.payload = payload;
        
    def createPacket(self, key):            
        signedPart = chr(self.type) + chr(self.version) + "\0\0"
        signedPart += str(self.deviceId)
        iv = str(struct.pack("<Q", self.counter1)) + str(struct.pack("<Q", self.counter2))
        signedPart += iv
        signedPart += encrypt(self.payload, key, iv)
        hmac = hmacsha256(signedPart, key)        
        packet = "IOT\0" + hmac + signedPart
        return packet

def hmacsha256(data, key):
    return hmac.new(key, data, digestmod=hashlib.sha256).digest()

def encrypt(plain, key, iv):
    #padding
    padnum = 16 - (len(plain) % 16)
    padded = plain + chr(padnum)*padnum
    
    #encrypting
    crypto = AES.new(key, AES.MODE_CBC, iv)
    encryptedBytes = crypto.encrypt(padded)    	 
    return encryptedBytes
    
def decrypt(data, key, iv):
     #decrypting
     crypto = AES.new(key, AES.MODE_CBC, iv)
     decryptedBytes = crypto.decrypt(data)  
     
     #unpadding
     decryptedBytes = decryptedBytes[:-ord(decryptedBytes[-1])]
     return decryptedBytes
     
def deriveKey(masterKey, deviceId):
    return hmacsha256(deviceId, masterKey)
    
def configureLogging(level, console, file):
    logger = logging.getLogger()    
    logger.setLevel(level)
    formatter = logging.Formatter('%(asctime)s  %(levelname)s   %(message)s')
    if console:
        cons = logging.StreamHandler()
        cons.setLevel(level)
        cons.setFormatter(formatter)
        logger.addHandler(cons)
        print("logging to console")
        
    if file:              
        f = logging.FileHandler(file)        
        f.setLevel(level)
        f.setFormatter(formatter)
        logger.addHandler(f)        
        print("logging to file {0}".format(file))

def recvBytes(sock, count):
    buf = b''
    while count:
        newbuf = sock.recv(count)
        if not newbuf: return None
        buf += newbuf
        count -= len(newbuf)
    return buf        
    
def sendMessage(sock, data):
    length = len(data)
    sock.sendall(struct.pack('<I', length))
    sock.sendall(data)

def recvMessage(sock):
    lengthbuf = recvBytes(sock, 4)
    length = struct.unpack('<I', lengthbuf)[0]
    return recvBytes(sock, length)    
    
def domainToIp(address):
    host = address.split(':')[0]
    port = address.split(':')[1]
    try:
        socket.inet_aton(host)  
        return address        
    except socket.error:
        host = socket.gethostbyname(host)
        return host + ':' + port
        
def getFullPath(path):
    #dir = os.path.dirname(os.path.realpath(__file__))
    dir = os.getcwd()
    if path[0] != '/':
        return dir + '/' + path
    else:
        return path