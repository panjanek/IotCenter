# IotCenter

Simple, lightweight, python-based management service for IoT devices for makers and hobbysts with SSL security and python tornado web UI

Work in progress...

## About this project

### Motivation

When creating hobby IoT projects based on linux embeded platforms (like Raspberry PI, Onion, Arietta, CHIP, ...) or microcontroller platform (like Arduino, esp2866, Photon, ...) sooner or later one have to use some kind of management service to collect data from sensors and send commands to devices. If the devices are placed in remote locations, behind NAT or 3G network, the task of establishing reliable and secure two-way link between the device and management server is not trivial. 

Existing IoT clouds are great, but are usually dedicated to specific device brand (like Photon) or big and feature rich or SaaS, which makes them difficult (or impossible) to install and configure on one's own hardware.

This project aims for creating simple, manageble and portable server application for collecting data from devices and sending commands to devices. The application is written in python and can be run as a daemon on any linux system, for example Raspberry Pi. Second part of the project is the device part in form of client python script that runs as a daemon on the device side and is responsible for establishing secure socket link to the server, authenticating and handling communication. In order to read data from sensors or handle custom commands from the server one havr to implement few lines of customized python code.

### How it works
 - server.py script runs as daemon and exposes SSL endpoint for devices to connect
 - client.py script runs as daemon on a device and connects to configured server SSL endpoint
 - once the link is established, server lists the device in web GUI
 - device sends readings to the server
 - server presents the readings in web GUI
 - web GUI supports sending commands to specific device
 - pluggable device script device/app.py handles commands
 
### Features
 - server-device communication by SSL TCP socket (for linux devices). Secure communication with two way certificate authentication
 - alternative communication by encrypted UDP packets (for microcontrollers). Secure communication with SHA256 encryption and HMAC-SHA256 authentication.
 - customizable device part: sensor reading part and command handling in form of python script
 - WWW UI based on pure css, tornado and WebSockets
 - Sensor readings storing in sqlite
 - Sensor readings reports as google charts
 - For linux devices support for SSH tunnel command for logging by SSH into the device behind NAT or 3G

### TODO / Roadmap
 - device implementation for Arduino using encrypted UDP communication
 - external display support for server side script

## Usage
 
 TODO
