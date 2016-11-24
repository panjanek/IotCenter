import logging
import json
import sqlite3
import datetime

class Database:
    logger = logging.getLogger()

    def __init__(self, dbFile):
        self.dbFile = dbFile
        
    def save(self, deviceIdHex, sensor, protocol, ip, time, numberValue):
        self.logger.debug("saving to db: device={0}, sensor={1}, protocol={2} ip={3}, time={4}, numberValue={5}".format(deviceIdHex, sensor, protocol, ip, time, numberValue))
        try:
            conn = sqlite3.connect(self.dbFile)
            deviceId = self.getDeviceId(conn, deviceIdHex)
            sensorId = self.getSensorId(conn, sensor)
            addressId = self.getAddressId(conn, protocol, ip)
            self.saveReading(conn, deviceId, sensorId, addressId, time, numberValue)
            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.exception(e)
            
              
    def saveReading(self, conn, deviceId, sensorId, addressId, time, numberValue):
        c = conn.cursor()
        if self.doesTableExist(conn, "readings"):
            pass
        else:
            self.logger.info("Creating table 'readings'")
            c.execute('CREATE TABLE readings (id INTEGER PRIMARY KEY AUTOINCREMENT, time DATETIME NOT NULL, year INTEGER NOT NULL, month INTEGER NOT NULL, day INTEGER NOT NULL, hour INTEGER NOT NULL, minute INTEGER NOT NULL, deviceId INTEGER NOT NULL, sensorId INTEGER NOT NULL, addressId INTEGER NOT NULL, numberValue REAL, FOREIGN KEY(deviceId) REFERENCES devices(id), FOREIGN KEY(sensorId) REFERENCES sensord(id), FOREIGN KEY(addressId) REFERENCES addresses(id))')      
            c.execute("CREATE INDEX idx_readings_time ON readings(time)")            
            c.execute("CREATE INDEX idx_readings_deviceId ON readings(deviceId)")
            c.execute("CREATE INDEX idx_readings_sensorId ON readings(sensorId)")
            c.execute("CREATE INDEX idx_readings_addressId ON readings(addressId)")            
        #.strftime('%Y-%m-%d %H:%M:%S')
        c.execute("INSERT INTO readings(time, year, month, day, hour, minute, deviceId, sensorId, addressId, numberValue) VALUES(?,?,?,?,?,?,?,?,?,?)", (time, time.year, time.month, time.day, time.hour, time.minute, deviceId, sensorId, addressId, numberValue))
        
    def getChartData(self, sensors, timeFrom, timeTo, aggregation):      
        timeFormat = "%Y-%m-%d %H:%M"
        groupingColumns = "year, month, day, hour, minute"
        intervalSeconds = 60
        if aggregation == "hour":
            timeFormat = "%Y-%m-%d %H"
            groupingColumns = "year, month, day, hour"
            intervalSeconds = 3600
        elif aggregation == "day":
            timeFormat = "%Y-%m-%d"
            groupingColumns = "year, month, day"  
            intervalSeconds = 24*3600      
        
        conn = sqlite3.connect(self.dbFile)
        c = conn.cursor()
        conditions = []
        for sensor in sensors:
            conditions.append(" (devices.hex = '{0}' AND sensors.name='{1}') ".format(sensor.deviceId, sensor.sensorId))
        sourcesCondition = " OR ".join(conditions)
        query = "SELECT devices.hex, sensors.name, {0}, AVG(numberValue) FROM readings JOIN devices ON readings.deviceId=devices.id JOIN sensors ON readings.sensorId=sensors.id WHERE ({1}) AND readings.time>=? AND readings.time<=? GROUP BY devices.hex, sensors.name, {0} ORDER BY {0}".format(groupingColumns, sourcesCondition)
        self.logger.debug("Executiong query: {0}".format(query))
        data = {}
        dbRowsCount = 0
        for row in c.execute(query, (timeFrom, timeTo)):
            dbRowsCount += 1
            timeKey = ""
            valueIdx = 7
            if aggregation == "day":
                timeKey = "{0:04d}-{1:02d}-{2:02d}".format(row[2], row[3], row[4])
                valueIdx = 5
            elif aggregation == "hour":
                timeKey = "{0:04d}-{1:02d}-{2:02d} {3:02d}".format(row[2], row[3], row[4], row[5])
                valueIdx = 6
            else:
                timeKey = "{0:04d}-{1:02d}-{2:02d} {3:02d}:{4:02d}".format(row[2], row[3], row[4], row[5], row[6])
                valueIdx = 7
            fields = {"time": timeKey, "numberValue": row[valueIdx], "deviceId":row[0], "sensorId":row[1]}
            source = "{0}.{1}".format(fields["deviceId"], fields["sensorId"])
            if not fields["time"] in data:
                data[fields["time"]] = {}
            data[fields["time"]][source] = {"numberValue":fields["numberValue"]}  
        if len(data) == 0:
            return []
        minTimeStr = min(data.items(),key=lambda x: x[0])[0]
        maxTimeStr = max(data.items(),key=lambda x: x[0])[0]
        self.logger.debug("{0} raw data rows loaded from db and processed to give {1} time keys for period {2} - {3}".format(dbRowsCount, len(data), minTimeStr, maxTimeStr))
        minTime = datetime.datetime.strptime(minTimeStr, timeFormat)
        maxTime = datetime.datetime.strptime(maxTimeStr, timeFormat)
        timeKeysCount = 0
        emptyCount = 0
        chartData = []
        for singleTime in self.daterange(minTime, maxTime, intervalSeconds):
            timeKeysCount += 1
            timeKey = singleTime.strftime(timeFormat)
            if timeKey not in data:
                data[timeKey] = {}
                emptyCount += 1
            data[timeKey]["time"] = timeKey
            chartData.append(data[timeKey])  
        self.logger.debug("There are {0} time points in period {1} - {2}. {3} empty time points added.".format(timeKeysCount, minTimeStr, maxTimeStr, emptyCount))
        conn.close()
        return chartData
        
    def getDevicesData(self):
        conn = sqlite3.connect(self.dbFile)
        c = conn.cursor()
        devicesData = {}
        for row in c.execute("SELECT devices.id, devices.hex, max(readings.time) FROM devices JOIN readings ON devices.id = readings.deviceId GROUP BY devices.id, devices.hex"):
            did = row[0]
            devDict = {"deviceId":str(row[1].encode('UTF-8')), "lastContact":row[2]}
            devDict["values"] = {}
            c2 = conn.cursor()
            for sensor in c2.execute("SELECT sensors.name, readings.numberValue, addresses.ip, addresses.protocol FROM readings JOIN sensors ON readings.sensorId = sensors.id JOIN addresses ON readings.addressId = addresses.id WHERE readings.time=? AND deviceId=?", (devDict["lastContact"],did)):
                devDict["address"] = sensor[2]
                devDict["protocol"] = sensor[3]
                devDict["values"][sensor[0]] = sensor[1]
            devicesData[devDict["deviceId"]] = devDict           
        conn.close()
        return devicesData
            
    def daterange(self, startDate, endDate, intervalSeconds):
        for n in range(int ((endDate - startDate).total_seconds() / intervalSeconds) + 2):
            yield startDate + datetime.timedelta(seconds=n*intervalSeconds)            
            
    def getDeviceId(self, conn, deviceIdHex):
        c = conn.cursor()
        if self.doesTableExist(conn, "devices"):
            pass
        else:
            self.logger.info("Creating table 'devices'")
            c.execute('CREATE TABLE devices (id INTEGER PRIMARY KEY AUTOINCREMENT, hex TEXT NOT NULL)')
        c.execute('SELECT id FROM devices WHERE hex=?', (deviceIdHex,))
        record = c.fetchone()
        if record:
            return record[0]
        else:
            self.logger.info('Device {0} does not exist in db. Creating device record'.format(deviceIdHex))
            c.execute('INSERT INTO devices(hex) VALUES(?)', (deviceIdHex,))     
            return c.lastrowid
            
    def getSensorId(self, conn, sensor):
        c = conn.cursor()
        if self.doesTableExist(conn, "sensors"):
            pass
        else:
            self.logger.info("Creating table 'sensors'")
            c.execute('CREATE TABLE sensors (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL)')
        c.execute('SELECT id FROM sensors WHERE name=?', (sensor,))
        record = c.fetchone()
        if record:
            return record[0]
        else:
            self.logger.info('Sensor {0} does not exist in db. Creating sensor record'.format(sensor))
            c.execute('INSERT INTO sensors(name) VALUES(?)', (sensor,))     
            return c.lastrowid    

    def getAddressId(self, conn, protocol, ip):
        c = conn.cursor()
        if self.doesTableExist(conn, "addresses"):
            pass
        else:
            self.logger.info("Creating table 'addresses'")
            c.execute('CREATE TABLE addresses (id INTEGER PRIMARY KEY AUTOINCREMENT, protocol TEXT NOT NULL, ip TEXT NOT NULL)')
        c.execute('SELECT id FROM addresses WHERE protocol==? AND ip=?', (protocol, ip))
        record = c.fetchone()
        if record:
            return record[0]
        else:
            self.logger.info('Address {0}/{1} does not exist in db. Creating address record'.format(protocol, ip))
            c.execute('INSERT INTO addresses(protocol, ip) VALUES(?, ?)', (protocol, ip))     
            return c.lastrowid 
            
    def doesTableExist(self, conn, tableName):
        if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tableName,)).fetchone():
            return True
        else:
            self.logger.info("Table '{0}' does not exist.".format(tableName))
            return False
          