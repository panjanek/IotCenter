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
        
    def saveTrends(self, trends):
        time = datetime.datetime.now()
        mintime = time - datetime.timedelta(minutes=30)
        for value in self.values:
            key = "{0}.{1}".format(self.deviceId, value.id)
            if not key in trends:
                trends[key] = []
            trends[key].append(SensorTimedValue(time, value.value))
            trends[key] = filter(lambda x: x.time > mintime, trends[key])
            trends[key].sort(key=lambda r: r.time, reverse=True)
            
    def computeTrends(self, trends):
        time = datetime.datetime.now()
        t1 = time - datetime.timedelta(minutes=3)
        t2 = time - datetime.timedelta(minutes=10)
        for value in self.values:
            key = "{0}.{1}".format(self.deviceId, value.id)
            if key in trends and len(trends[key])>2:
                previous = filter(lambda x: x.time > t2 and x.time <= t1, trends[key])
                current = filter(lambda x: x.time > t1 and x.time <= time, trends[key])
                if len(previous) >= 5 and len(current) >= 2:
                    previous_values = [x.value for x in previous]
                    previous_avg = sum(previous_values)/len(previous_values)
                    current_values = [x.value for x in current]
                    current_avg = sum(current_values)/len(current_values)
                    if current_avg > previous_avg + 0.1:
                        value.trend = 1
                    if current_avg < previous_avg - 0.1:
                        value.trend = -1
                        
                    #print "previous: {0}".format(previous)
                    #print "previous numbers: {0}".format([x.value for x in previous])
                    #print "previous avg: {0}".format(previous_avg)
                    #print "current: {0}".format(current)
                    #print "current numbers: {0}".format([x.value for x in current])
                    #print "current avg: {0}".format(current_avg)
                    #print "---- {0}: {1}".format(key, value.trend)
        return self
    
    
    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)    
        
class SensorTimedValue:
    def __init__(self, time, value):
        self.time=time
        self.value=value

    def __str__(self):
        return "<{0} - {1}>".format(self.time.strftime('%Y-%m-%d %H:%M:%S'), self.value)
        
    def __unicode__(self):
        return self.__str__()
        
    def __repr__(self):
        return self.__str__()

class SensorValue:
    def __init__(self, id, label, value, unit):
        self.id = id
        self.label = label
        self.value = value
        self.unit = unit
        self.trend = None
        
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