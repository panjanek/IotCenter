from iotprotocol.iotclient import IotClientService
from iotprotocol.iotcommon import getFullPath
from iotprotocol.iotcommon import configureLogging
from iotprotocol.iotcommon import domainToIp
from iotprotocol.daemon import Daemon
import logging
import ConfigParser
import os
import argparse
import importlib

if __name__ == "__main__":
    confFile = getFullPath('conf/client.conf')    
    parser = argparse.ArgumentParser(description='IoT UDP Protocol client')    
    parser.add_argument('-c', type=str, dest='config_file', help='client config file', default=confFile)         
    parser.add_argument('command', type=str, help='[start] ,[stop] or [restart] the client as daemon or [run] the client in cosole mode', default='start', choices = ['start', 'stop', 'restart', 'run'])        
    args = parser.parse_args()     
    confFile = getFullPath(args.config_file)
    if not os.path.exists(confFile):
        print('Missing config file at {0}'.format(confFile))
        exit()    
    print('using config at {0}'.format(confFile))
    config = ConfigParser.ConfigParser()
    config.read(confFile)      
    logLevel = logging.getLevelName(config.get('log', 'logLevel'))
    deviceId = buffer(bytearray.fromhex(config.get('client', 'deviceId')))
    deviceKey = buffer(bytearray.fromhex(config.get('client', 'deviceKey')))    
    serverAddr = domainToIp(config.get('client', 'serverAddr'))
    protocol = config.get('client', 'protocol')
    pidFile = getFullPath(config.get('client', 'pidFile'))    
    if not deviceId or not deviceKey:
        print("deviceId or deviceKey missing in file {0}. Use 'python server.py newdevice' command on your server in order to get deviceId,deviceKey pair".format(confFile))
        exit()    

    logFile = config.get('log', 'logFile')
    if logFile:
        logFile = getFullPath(logFile)
    configureLogging(logLevel, config.get('log', 'logToConsole'), logFile)
    logger = logging.getLogger() 
    deviceHandlerConf = config.get('client', 'deviceHandler')  
    handlerPath = ".".join(deviceHandlerConf.split('.')[:-1])
    handlerClassName = deviceHandlerConf.split('.')[-1]    
    logger.info("Creating instance of device handler: module={0}, class={1}".format(handlerPath, handlerClassName))
    mod = __import__(handlerPath, fromlist=[handlerClassName])
    deviceHandlerClass = getattr(mod, handlerClassName)
    deviceHandler = deviceHandlerClass(config)
    client = IotClientService(protocol, serverAddr, deviceId, deviceKey, deviceHandler)
    if config.has_option('udp', 'stateFile'):       
        client.stateFile = getFullPath(config.get('udp', 'stateFile'))
    if config.has_option('udp', 'udpHeartbeatSeconds'):       
        client.udpHeartbeatSeconds = int(config.get('udp', 'udpHeartbeatSeconds'))
    if config.has_option('udp', 'udpDataPacketInterval'):       
        client.udpDataPacketInterval = int(config.get('udp', 'udpDataPacketInterval'))  
    if config.has_option('ssl', 'sslIntervalSeconds'):       
        client.sslIntervalSeconds = int(config.get('ssl', 'sslIntervalSeconds'))          
    if config.has_option('ssl', 'caCertFile'):       
        client.caCertFile = getFullPath(config.get('ssl', 'caCertFile'))      
    if config.has_option('ssl', 'deviceCertFile'):       
        client.deviceCertFile = getFullPath(config.get('ssl', 'deviceCertFile'))    
    if config.has_option('ssl', 'deviceKeyFile'):       
        client.deviceKeyFile = getFullPath(config.get('ssl', 'deviceKeyFile'))

    if args.command == "run":    
        logger.info("Running client in console mode")
        client.start()
    elif args.command == "restart":
        logger.info("restarting client in daemon mode")
        daemon = Daemon(pidFile, client.start)
        daemon.restart()
    elif args.command == "stop":
        print("Stopping client in daemon mode")
        daemon = Daemon(pidFile, client.start)
        daemon.stop()
    else:
        logger.info("Starting client in daemon mode")
        daemon = Daemon(pidFile, client.start)
        daemon.start()    