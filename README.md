# IotCenter

Simple, lightweight, python-based management service for IoT devices for makers and hobbysts with SSL security and tornado web UI

Work in progress...

## About this project

### Motivation

When creating hobby IoT projects based on linux embeded platforms (like [Raspberry Pi](https://www.raspberrypi.org/), [Onion](https://onion.io/), [Arietta](http://www.acmesystems.it/arietta), [CHIP](https://getchip.com/), ...) or microcontroller platform (like [Arduino](https://www.arduino.cc/), [esp2866](http://www.esp8266.com/), [Photon](https://www.particle.io/), ...) sooner or later one have to use some kind of management service to collect data from sensors and send commands to devices. If the devices are placed in remote locations, behind NAT or 3G network, the task of establishing reliable and secure two-way link between the device and management server is not trivial. 

Existing IoT clouds are great, but are usually dedicated to specific device brand (like Photon) or big and feature rich or SaaS, which makes them difficult (or impossible) to install and configure on one's own hardware.

This project aims for creating simple, manageble and portable server application for collecting data from various brands and types of devices and sending commands to the devices. The application is written in python and can be run as a daemon on any linux system, for example Raspberry Pi. Second part of the project is the device part in form of client python script that runs as a daemon on the device side and is responsible for establishing secure socket link to the server, authenticating and handling communication. In order to read data from sensors or handle custom commands from the server one have to implement few lines of customized python code.

### How it works
 - server.py script runs as daemon and exposes SSL endpoint for devices to connect
 - client.py script runs as daemon on a device and connects to configured server SSL endpoint
 - once the link is established, server lists the device in web GUI
 - device sends readings to the server
 - server saves the readings in sqline and presents the reports in web GUI
 - web GUI supports sending commands to specific device
 - pluggable device script device/app.py handles commands
 
### Features
 - server-device communication by SSL TCP socket (for linux devices). Secure communication with two way certificate authentication
 - alternative communication by encrypted UDP packets (for microcontrollers). Secure communication with SHA256 encryption and HMAC-SHA256 authentication.
 - customizable device part: sensor reading part and command handling in form of python script
 - WWW UI based on [Pure.css](http://purecss.io/), [tornado](http://www.tornadoweb.org/en/stable/) and WebSockets
 - Sensor readings storing using [sqlite](https://sqlite.org/)
 - Sensor readings reports using [Google Charts](https://developers.google.com/chart/)
 - For linux devices support for SSH tunnel command for logging by SSH into the device behind NAT or 3G
 - Customization by writing plugins in python

### TODO / Roadmap
 - implement client for Arduino using encrypted UDP communication
 - add external display support for server side script to use on Raspbery Pi with small [LCD screen](http://www.waveshare.com/3.5inch-rpi-lcd-a.htm)

## Usage

TODO

1. Install dependencies: tornado, sqlite, ...
2. Download IotCenter scripts
3. Setup initial server configuration: python server.py init
4. Create device configuration: python server.py newdevice
5. Run the server: python server.py start
6. Copy configuration to device and run device client daemon: python client.py start


