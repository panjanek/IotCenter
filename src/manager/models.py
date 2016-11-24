import datetime
import json
import os
import binascii

class DeviceModel:
    def __init__(self):
        self.deviceId = None
        self.protocol = None
        self.lastContact = None
        self.address = None
        self.values = []
        self.commands = []
        self.images = []
        self.name = None       
        self.isOnline = False
    
    def loadFromSession(self, session, deviceConfig, payloadDict):
        self.deviceId = binascii.hexlify(session.deviceId)
        self.protocol = session.protocol
        self.lastContact = session.lastUpdateTime.strftime('%Y-%m-%d %H:%M:%S')
        self.address = "{0}:{1}".format(session.clientAddr[0], session.clientAddr[1])
        self.values = []
        self.commands = []
        self.images = []
        self.isOnline = True
        conf = deviceConfig.get(self.deviceId, None)
        if conf:
            self.name = conf.get("name", self.deviceId)
        if payloadDict:
            if "values" in payloadDict:
                for attr, value in payloadDict["values"].items():
                    if conf:
                        varConf = conf.get("values", {}).get(attr, {})
                        self.values.append(SensorValue(attr, varConf.get("label", attr), value, varConf.get("unit")))
                    else:
                        self.values.append(SensorValue(attr, attr, value, ""))
        return self
        
    def loadFromDict(self, devDict, deviceConfig):
        self.deviceId = devDict["deviceId"]
        self.protocol = devDict["protocol"]
        self.address = devDict["address"] 
        self.lastContact = devDict["lastContact"].split('.')[0]
        conf = deviceConfig.get(self.deviceId, None)
        if conf:
            self.name = conf.get("name", self.deviceId)
        if "values" in devDict:
            for attr, value in devDict["values"].items():
                if conf:
                    varConf = conf.get("values", {}).get(attr, {})
                    self.values.append(SensorValue(attr, varConf.get("label", attr), value, varConf.get("unit")))
                else:
                    self.values.append(SensorValue(attr, attr, value, ""))        
        return self
        
    def loadCommands(self, deviceConfig):
        conf = deviceConfig.get(self.deviceId, None)
        if conf:
            self.commands = conf["commands"]
        return self
        
    def loadImages(self, imagesDir, count):
        files = [s for s in os.listdir(imagesDir) if os.path.isfile(os.path.join(imagesDir, s))]
        files.sort(key=lambda s: os.path.getmtime(os.path.join(imagesDir, s)), reverse=True)
        files = files[:count]
        self.images = [UploadedImage("/upload/{0}/images/{1}".format(self.deviceId, file), os.path.join(imagesDir, file), datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(imagesDir, file))).strftime('%Y-%m-%d %H:%M:%S')) for file in files]   
        return self        
    
    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)    

class SensorValue:
    def __init__(self, id, label, value, unit):
        self.id = id
        self.label = label
        self.value = value
        self.unit = unit
        
class UploadedImage:
    def __init__(self, url, file, date):
        self.url = url
        self.file = file
        self.date = date
        
class SensorFilter:
    def __init__(self, deviceId, deviceName, sensorId, sensorLabel, dataType, selected):
        self.deviceId = deviceId
        self.deviceName = deviceName  
        self.sensorId = sensorId
        self.sensorLabel = sensorLabel
        self.selected = selected
        self.dataType = dataType
        self.fullId = "{0}.{1}".format(self.deviceId, self.sensorId)