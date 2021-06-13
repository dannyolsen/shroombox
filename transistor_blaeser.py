
#Author: Danny Olsen
#Date started: 21-09-2018
#Date revised: 21-01-2021
#Controlling Metz MR-DO4 modbus output module

#Structure of program
    #1  IMPORTED LIBRARIES
    #2  GLOBAL VARIABLES

    #4  FUNCTIONS
    #5  MAIN PROGRAM

#************************************************** 1 IMPORTED LIBRARIES **************************************************
import minimalmodbus
import os
import numbers
import types
import sys

#Detecting operating system and will setup the modbus com port to fit the os
if(os.name == 'nt') :      #windows
    modbus_port = 'COM6'
    pass
elif(os.name == 'posix'):  #debian on raspberry pi
    modbus_port = '/dev/ttyUSB0'
    pass

#************************************************** 2 GLOBAL VARIABLES **************************************************



#************************************************** 4 FUNCTIONS **************************************************

def writeMR_DO4(modbus_adr,relay_no,state): #Modbus adressen skal specificeres samt hvilket relæ der ønskes sluttet. State er 1 eller 0
    #dev_name = "MR-DO4"
    
    #Setting up modbus
    MR_DO4 = minimalmodbus.Instrument(port=modbus_port, slaveaddress=modbus_adr, mode='rtu') #The COM port on which the modbus reader communicates on (fx. USB-COMi-TB)
    MR_DO4.serial.baudrate=19200
    MR_DO4.serial.timeout=1
    MR_DO4.serial.parity= 'E'
    MR_DO4.debug=False

    MR_DO4.write_bit(registeraddress=relay_no,value=state,functioncode=5)

#************************************************** 5 MAIN PROGRAM **************************************************

#writeMR_DO4(3,3,0)
