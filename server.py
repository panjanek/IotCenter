from iotprotocol.iotserver import IotServerService
from iotprotocol.iotcommon import getFullPath
from iotprotocol.iotcommon import configureLogging
from iotprotocol.iotcommon import deriveKey
from iotprotocol.iotcommon import hmacsha256
from iotprotocol.daemon import Daemon
import binascii
import logging
import ConfigParser
import os
import argparse      
import importlib
import bcrypt
import getpass
import sys

if __name__ == "__main__":
    confFile = getFullPath('conf/server.conf')    
    parser = argparse.ArgumentParser(description='IoT UDP Protocol server')    
    parser.add_argument('-c', type=str, dest='config_file', help='server config file', default=confFile)         
    parser.add_argument('command', type=str, help='[start] ,[stop] or [restart] the server as daemon or [run] the server in cosole mode or create configuration for [newdevice] or [init] fresh server configuration', default='start', choices = ['start', 'stop', 'restart', 'run', 'newdevice','init'])         
    args = parser.parse_args()         
    confFile = getFullPath(args.config_file)     
    if not os.path.exists(confFile) and args.command != 'init':
        print("Missing config file at {0}. Use 'python server.py init' to generate initial configuration or supply existing conf file with -c".format(confFile))
        exit()
    else:
        print('using config at {0}'.format(confFile))
           
    if args.command == "init":
        if os.path.exists(confFile):
            print("Configuration file {0} exists.".format(confFile))
        else:
            confDir = os.path.dirname(confFile)
            if not os.path.exists(confDir):
                os.makedirs(confDir)
            serverName = raw_input('Enter server name (ex. domain name) for SSL certificate:')
            sys.stdout.write("Enter password for UI:")
            uiPassword = getpass.getpass()
            sys.stdout.write("Repeat password for UI:")
            uiPassword2 = getpass.getpass()
            adminPasswordHash = bcrypt.hashpw(uiPassword, bcrypt.gensalt())
            if uiPassword != uiPassword2:
                print("Passwords don't match.")
                exit()
            print("Creating initial configuration")
            masterKey = os.urandom(64)
            serverCertFile = getFullPath(os.path.join(confDir, 'servercert.pem'))  
            serverKeyFile = getFullPath(os.path.join(confDir, 'serverkey.pem'))              
            os.system('openssl req -x509 -newkey rsa:2048 -keyout {0} -out {1} -days 36500 -subj "/C=NA/ST=NA/L=NA/O=IOT/CN={2}" -nodes'.format(serverKeyFile, serverCertFile, serverName))            
            serverConf = '[server]\n'
            serverConf += 'masterKey = '+binascii.hexlify(masterKey) + '\n'
            serverConf += 'serverHandler = manager.app.IotManager\n'
            serverConf += 'pidFile = /tmp/iots.pid\n'
            serverConf += 'serverName = ' + serverName + '\n\n'
            serverConf += '[ssl]\n'    
            serverConf += 'sslListenAddr = 0.0.0.0:9998\n'            
            serverConf += 'caCertFile = ' + serverCertFile + '\n'
            serverConf += 'serverCertFile = ' + serverCertFile + '\n'
            serverConf += 'serverKeyFile = ' + serverKeyFile + '\n\n'
            serverConf += '[udp]\n'                
            serverConf += 'stateFile = {0}\n'.format(os.path.join(confDir, 'server.dat'))
            serverConf += 'udpListenAddr = 0.0.0.0:9999\n\n'
            serverConf += '[web]\n'
            serverConf += 'httpsPort = 443\n'
            serverConf += 'httpPort = 80\n'
            serverConf += 'adminPasswordHash = {0}\n'.format(adminPasswordHash)
            serverConf += 'uploadDir = /tmp/iot-uploads\n'
            serverConf += 'dbFile = {0}\n'.format(os.path.join(confDir, 'iot.db'))
            serverConf += 'httpsCertFile = ' + serverCertFile + '\n'
            serverConf += 'httpsKeyFile = ' + serverKeyFile + '\n'    
            serverConf += 'httpsChainFile = \n'   
            serverConf += 'localVideoPort = 8081\n\n'            
            serverConf += '[log]\n'                
            serverConf += 'logLevel = DEBUG\n'
            serverConf += 'logToConsole = True\n'
            serverConf += 'logFile = /tmp/iotserver.log\n\n'  
            serverConf += '[devices]\n'          
            with open(confFile, 'w') as f:
                f.write(serverConf)                       
            print("Generated 3 server files:\n    {0}\n    {1}\n    {2}\n".format(confFile, serverCertFile, serverKeyFile))
            print("Config saved in {0}:".format(confFile))              
    else:    
        config = ConfigParser.ConfigParser()
        config.read(confFile)      
        logLevel = logging.getLevelName(config.get('log', 'logLevel'))
        udpListenAddr = config.get('udp', 'udpListenAddr')    
        sslListenAddr = config.get('ssl', 'sslListenAddr')    
        masterKey = buffer(bytearray.fromhex(config.get('server', 'masterKey')))
        caCertFile = getFullPath(config.get('ssl', 'caCertFile'))   
        serverCertFile = getFullPath(config.get('ssl', 'serverCertFile'))   
        serverKeyFile = getFullPath(config.get('ssl', 'serverKeyFile'))   
        pidFile = getFullPath(config.get('server', 'pidFile'))    
        if args.command == "newdevice":
            print('generating device certificate and key')
            deviceId = os.urandom(16)
            deviceKey = deriveKey(masterKey, deviceId)
            certSignature = hmacsha256(deviceId, deviceKey)        
            shortId = binascii.hexlify(deviceId)[:4]
            deviceConfigDir = getFullPath("conf-{0}".format(shortId))
            os.makedirs(deviceConfigDir)
            deviceKeyFile = os.path.join(deviceConfigDir,'devicekey.pem')  
            deviceCsrFile = os.path.join(deviceConfigDir,'device.csr')  
            os.system('openssl req  -newkey rsa:2048 -nodes -keyout {0} -out {1} -subj "/C=NA/ST=NA/L=NA/O=IOT/CN={2}/description={3}"'.format(deviceKeyFile, deviceCsrFile, binascii.hexlify(deviceId), binascii.hexlify(certSignature)))
            deviceCertFile = os.path.join(deviceConfigDir,'devicecert.pem')  
            os.system('openssl x509 -req -in {0} -CA {1} -CAkey {2} -CAcreateserial -out {3} -days 36500 -sha256'.format(deviceCsrFile, serverCertFile, serverKeyFile, deviceCertFile))
            os.remove(deviceCsrFile)
            sshPrivateKeyFile = os.path.join(deviceConfigDir, 'iot_ssh')
            os.system("ssh-keygen -t rsa -f {0} -N ''".format(sshPrivateKeyFile))
            caCertFileCopy = os.path.join(deviceConfigDir, 'servercert.pem')
            os.system('cp {0} {1}'.format(caCertFile,caCertFileCopy))
            deviceConfFile = os.path.join(deviceConfigDir,'client.conf')
            clientConf =  '[client]\n'
            clientConf += 'deviceId = '+binascii.hexlify(deviceId) + '\n'
            clientConf += 'deviceKey = '+binascii.hexlify(deviceKey) + '\n'
            clientConf += 'deviceHandler = device.app.DeviceHandler\n'
            clientConf += 'serverAddr = {0}:9998\n'.format(config.get('server','serverName'))
            clientConf += 'protocol = ssl\n'
            clientConf += '#serverAddr = {0}:9999\n'.format(config.get('server','serverName'))
            clientConf += '#protocol = udp\n'
            clientConf += 'sshPrivateKeyFile = {0}\n'.format(sshPrivateKeyFile)
            clientConf += 'pidFile = /tmp/iotc_{0}.pid\n\n'.format(shortId)
            clientConf += '[ssl]\n'        
            clientConf += 'caCertFile = ' + caCertFileCopy + '\n'
            clientConf += 'deviceCertFile = ' + deviceCertFile + '\n'
            clientConf += 'deviceKeyFile = ' + deviceKeyFile + '\n'
            clientConf += 'sslIntervalSeconds = 60\n\n'            
            clientConf += '[udp]\n'                
            clientConf += 'stateFile = {0}\n'.format(os.path.join(deviceConfigDir, 'client.dat'))
            clientConf += 'udpHeartbeatSeconds = 10\n'
            clientConf += 'udpDataPacketInterval = 6\n\n'
            clientConf += '[log]\n'                
            clientConf += 'logLevel = DEBUG\n'
            clientConf += 'logToConsole = True\n'
            clientConf += 'logFile = /tmp/iotclient.log\n\n'
            with open(deviceConfFile, 'w') as f:
                f.write(clientConf)                       
            print("Generated 5 device files:\n    {0}\n    {1}\n    {2}\n    {3}\n    {4}\n".format(deviceConfFile, deviceCertFile, deviceKeyFile, caCertFileCopy, sshPrivateKeyFile))
            print("Config saved in {0}:".format(deviceConfFile))
            print("For ssh tunnel authorization add device ssh key to athorized-keys by running this command:")
            print("    cat {0}.pub >> ~/.ssh/authorized_keys".format(sshPrivateKeyFile))            
        elif args.command == 'start' or args.command == 'run' or args.command == 'restart':         
            logFile = config.get('log', 'logFile')
            if logFile:
                logFile = getFullPath(logFile)    
            configureLogging(logLevel, config.get('log', 'logToConsole'), logFile)
            logger = logging.getLogger()         
            serverHandlerConf = config.get('server', 'serverHandler')         
            handlerPath = ".".join(serverHandlerConf.split('.')[:-1])
            handlerClassName = serverHandlerConf.split('.')[-1]
            logger.info("Creating instance of server handler: module={0}, class={1}".format(handlerPath, handlerClassName))
            mod = __import__(handlerPath, fromlist=[handlerClassName])
            serverHandlerClass = getattr(mod, handlerClassName)
            serverHandler = serverHandlerClass(config)          
            server = IotServerService(udpListenAddr, sslListenAddr, masterKey, serverHandler)
            if config.has_option('udp', 'stateFile'):       
                server.stateFile = getFullPath(config.get('udp', 'stateFile'))            
            server.caCertFile = caCertFile   
            server.serverCertFile = serverCertFile 
            server.serverKeyFile = serverKeyFile      
            if args.command == "run":            
                logger.info("Running server in console mode")
                server.start()
            elif args.command == 'restart':
                logger.info("restarting server in daemon mode")
                daemon = Daemon(pidFile, server.start)
                daemon.restart()
            else:                
                logger.info("Starting server in daemon mode")
                daemon = Daemon(pidFile, server.start)
                daemon.start()
        elif args.command == 'stop':
            print("Stopping server in daemon mode")
            daemon = Daemon(pidFile, None)
            daemon.stop()             
        else:
            print("Unkown command {0}".format(args.command))
