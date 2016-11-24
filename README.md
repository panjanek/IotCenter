# IotCenter

Simple, lightweight, python-based management service for IoT devices for makers and hobbysts with SSL security and python tornado web UI

Work in progress...

### How it works
 - server.py script runs as daemon and exposes SSL endpoint for devices to connect
 - client.py script runs as daemon on a device and connects to configured server SSL endpoint
 - once the link is established, server lists the device in web GUI
 - device sends readings to the server
 - server presents the readings in web GUI
 - web GUI supports sending commands to specific device
 - pluggable device script device/app.py handles commands
