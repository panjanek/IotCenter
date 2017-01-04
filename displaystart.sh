sleep 30
sudo xauth add $(xauth -f ~pi/.Xauthority list|tail -1)
sudo python /home/pi/IotCenter/display.py -c /home/pi/IotCenter/conf/display.conf start

