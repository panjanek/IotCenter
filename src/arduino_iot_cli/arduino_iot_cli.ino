#include <Crypto.h>
#include <AES.h>
#include <CBC.h>
#include <SHA256.h>
#include <string.h>
#include <EEPROM.h>
#include <SPI.h>         
#include <Ethernet.h>
#include <EthernetUdp.h>     
#include <VirtualWire.h>   

const byte receive_pin = 4;
byte mac[] = {  0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED };
IPAddress myIp(192, 168, 1, 150);
IPAddress serverIp(192, 168, 1, 134);
byte deviceId[] = {0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00};
byte key[]  = {0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00};

EthernetUDP Udp;
CBC<AES256> cbcaes256;
SHA256 sha256;
char packet[192];
byte padded[48];
long counter = 0;
char tmp1[10];
long tmp1c = 0;
char tmp2[10];
long tmp2c = 0;
long c = 0;

void setup() {
  // init radio
  vw_set_rx_pin(receive_pin);
  vw_set_ptt_inverted(true); // Required for DR3100
  vw_setup(2000);   // Bits per sec
  vw_rx_start();       // Start the receiver PLL running 
  

  //init ethernet
  Ethernet.begin(mac, myIp);
  Udp.begin(2345);
  
  Serial.begin(9600);
  tmp1[0] = 0;
  tmp2[0] = 0;
  
  //uncomment to reset EEPROM counter
  //EEPROM.write(0, 0);  EEPROM.write(1, 0);  EEPROM.write(2, 0);  EEPROM.write(3, 0);
  counter = (long)EEPROM.read(0) + (((long)EEPROM.read(1)) << 8) + (((long)EEPROM.read(2)) << 16) + (((long)EEPROM.read(3)) << 24) + 1;
}

void loop() {
    c++;
    radioReceive();     
    if (c%3000 == 0 && (tmp1[0] != 0 || tmp2[0] != 0)) { 
        if (tmp1[0] !=0 && tmp2[0] == 0)
        {
            sprintf((char*)padded, "{\"values\":{\"t1\":%s}}", tmp1);
        } 
        else if (tmp1[0] ==0 && tmp2[0] != 0)
        {
            sprintf((char*)padded, "{\"values\":{\"t2\":%s}}", tmp2);
        }
        else 
        {
            sprintf((char*)padded, "{\"values\":{\"t1\":%s,\"t2\":%s}}", tmp1, tmp2);
        }
        Serial.println((char*)padded);
    
        //encrypt and sign
        byte srclen = strlen((char*)padded);
        byte padnum = 16 - (srclen % 16);
        memset(padded+srclen, padnum, padnum);
        int paddedLen = srclen + padnum;

        memset(packet+56, 0, 16);
        packet[56] = counter & 0xFF;
        packet[57] = (counter & 0xFF00) >> 8;
        packet[58] = (counter & 0xFF0000) >> 16;
        packet[59] = (counter & 0xFF000000) >> 24;
        cbcaes256.clear();
        cbcaes256.setKey(key, 32);
        cbcaes256.setIV((uint8_t *)(packet+56), 16);
        memcpy(packet, "IOT\0", 4);
        packet[36] = 1;
        packet[37] = 1;
        packet[38] = 0;
        packet[39] = 0;
        memcpy(packet+40, deviceId, 16);
        cbcaes256.encrypt(((uint8_t*)packet)+72, (uint8_t*)padded, paddedLen);
        int len = 72+paddedLen;
        sha256.resetHMAC(key, 32);
        sha256.update(packet+36, len - 36);
        sha256.finalizeHMAC(key, 32, packet+4, 32);
    
        //send
        Udp.beginPacket(serverIp, 9999);
        Udp.write(packet, len);
        Udp.endPacket();
    
        //store counter in eeprom
        counter++;
        if (counter % 10 == 0) {
            EEPROM.write(0, packet[56]);
            EEPROM.write(1, packet[57]);
            EEPROM.write(2, packet[58]);
            EEPROM.write(3, packet[59]);    
        }
    }

    delay(10);
    if (c - tmp1c > 12000){
        tmp1[0]=0;
    }

    if (c-tmp2c > 12000) {
        tmp2[0]=0;
    }
}


void radioReceive()
{
    uint8_t buf[VW_MAX_MESSAGE_LEN];
    uint8_t buflen = VW_MAX_MESSAGE_LEN;
    if (vw_get_message(buf, &buflen))
    {
        buf[buflen]=0;
        Serial.println((char*)buf);
        if ((buflen > 5) && (buflen < 20) && (buf[0] == 'T') && (buf[1] == 'M') && (buf[2] == 'P') && (buf[3] == '1' || buf[3] == '2') && (buf[4] == '='))
        {
            if (buf[3] == '1') {
                memcpy(tmp1, buf+5, buflen-4);
                tmp1c = c;
            } else if (buf[3] == '2'){
                memcpy(tmp2, buf+5, buflen-4);
                tmp2c = c;
            }
        }     
    } 
}
