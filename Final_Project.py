###Name: Yiyu Qian
###ID: 26072996

import RPi.GPIO as GPIO
import urllib.request
import codecs
import csv
import threading
import Adafruit_DHT
from PCF8574 import PCF8574_GPIO
from Adafruit_LCD1602 import Adafruit_CharLCD
from time import time, sleep, strftime
from datetime import datetime, date, timedelta

GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False) # to disable warnings
GPIO.cleanup()

#set up LED
LED_Green = 22
GPIO.setup(LED_Green, GPIO.OUT) # Green_LED
GPIO.output(LED_Green, False) # LED off 

watering_time = 0 # global variable watering_time

control = 0 # global variable of water control: control = 0 watering mode deactiviated , control = 1 watering mode activiated

def Read_Sensor():

    #GPIO of DHT11 is 17

    humidity, temperature = Adafruit_DHT.read_retry(11, 17)  #return readings from DHT11 sensor

    #check whether errors happen
    #read again
    
    while (humidity < 0 or humidity == 0 or humidity > 100 ) or (temperature < 0 or temperature == 0):
        
        humidity, temperature = Adafruit_DHT.read_retry(11, 17)

    print("Humidity : %.2f \t Temperature : %.2f \n"%(humidity, temperature))

    return(humidity, temperature)

def destroy():
    lcd.clear()

#calculate the average temperature and humidity 
def get_Avg(humidity, temperature):
    
    avg_humidity = sum(humidity) / len (humidity)
    avg_temperature = sum(temperature)/ len(temperature) 

    return (avg_humidity, avg_temperature)


def CIMIS_data(Date, Hour):   #read data from CIMIS
    
    ftp = urllib.request.urlopen("ftp://ftpcimis.water.ca.gov/pub2/hourly/hourly075.csv")
    csv_file = csv.reader(codecs.iterdecode(ftp, 'utf-8'))

    data = [] #list stores dictionaries ex. each row of the csv file is considered as a dictionary

    date_list = [] # list stores all dates in csv file

    counter = 0; #count row number as index
    
   # store every row as a dictionary in the data list 
    for row in csv_file:
        d = dict(index = counter, Date = row[1], Hour = row[2], ETo = row[4], Air_Temperature = row[12], Rel_Hum = row[14])
        data.append(d)
        #append date in date_list
        if (row[1] not in date_list):
            date_list.append(row[1])
        counter += 1
        
    # special case  ex. 6/9/2020 0000  ->  6/8/2020 2400
    if (Hour == '0000'):        
        Hour = '2400'        
        Date = (date.today() - timedelta(days=1)).strftime('%m/%d/%Y')
        
        #modify the date format
        Date = Date.split('/')
        Date.insert(1,'/')
        Date.insert(3,'/')
        for i in range(len(Date)):
            if Date[i][0] == '0':
                Date[i] = Date[i][1:]

        Date = ''.join(Date)
       
    # get values of the corresponding date and hour 
    for element in data:
        if (element['Date'] == Date) and (element['Hour'] == Hour):
            ETo = element['ETo']
            Air_Temperature = element['Air_Temperature']
            Rel_Hum = element['Rel_Hum']
            row_index_E = element['index']
            row_index_T = element['index']
            row_index_H = element['index']

        
    # in case the CIMIS has not updated today's data yet. ex. 6/6/2020, 1:12, but CIMIS only has data up to 6/5/2020
    if (Date not in date_list):
        last_row = data[counter - 1]    # I use data from the bottom row's dictionary
        ETo = last_row['ETo']
        Air_Temperature = last_row['Air_Temperature']
        Rel_Hum = last_row['Rel_Hum']
        row_index_E = last_row['index']
        row_index_T = last_row['index']
        row_index_H = last_row['index']

    
    # in case the CIMIS has not updated the ETo yet, use the most recent hour's ETo
    while (ETo == '--'or ETo == '0'):
        row_index_E -= 1 #go back to the previous row 
        for element in data:
            if (element['index'] == row_index_E): #search the data of the previous row's dictionary
                ETo = element['ETo']
            

    # in case the CIMIS has not updated the Air_Temperature yet, use the most recent hour's Air_Temperature
    while (Air_Temperature == '--'):
        row_index_T -= 1 #go back to the previous row 
        for element in data:
            if (element['index'] == row_index_T): #search the data of the previous row's dictionary
                Air_Temperature = element['Air_Temperature']

    # in case the CIMIS has not updated the Rel_Hum yet, use the most recent hour's Rel_Hum
    while (Rel_Hum == '--'):
        row_index_H -= 1 #go back to the previous row 
        for element in data:
            if (element['index'] == row_index_H): #search the data of the previous row's dictionary
                Rel_Hum = element['Rel_Hum']
                                
    return ETo, Rel_Hum, Air_Temperature


# calculate the ET_station, ET_local and watering_time
def watering(ETo, CIMIS_Hum, avg_hum, CIMIS_Temperature, avg_temp):
        
    ET_station = (ETo * 1 * 200 * 0.62) / 0.75   #gallons of water per hour 
    
    # derate ET_local
    ET_local = ET_station/((avg_hum / CIMIS_Hum) * (avg_temp / CIMIS_Temperature))  #gallons of water per hour
    
    # water debit 1020 gallons/h
    watering_time = (ET_local * 24 / 1020) # water irrigation hours per day
    watering_time = watering_time * 3600 # water irrigation seconds per day
    watering_time = watering_time / 24 # water irrigation seconds per hour
        
    return ET_station, ET_local, watering_time

# target function of irrigation thread
def irrigate():

    global control
         
    while True:

        if control == 0: # watering mode deactiviated, watering off 
            
            continue
        
        else: # watering mode activiated

            if watering_time > 0: # irrigation will only happen if watering time is greater than 0 
                
                print("water on \n")

                destroy()
                lcd.setCursor(0,0) # set cursor position
            
                lcd.message( 'Water on\n' )

                t_end = time() + watering_time # set up a timer 

                while time() < t_end:  # watering 
                
                    GPIO.output(LED_Green, True) # turn on LED to virtualize irrigation
         
                GPIO.output(LED_Green, False) # turn off LED to virtualize watering off 
            
            print("water off\n")

            destroy()
            lcd.setCursor(0,0) # set cursor position
            
            lcd.message( 'Water off\n' )

            control = 0 # watering mode deactiviated
            

# target function of sense thread                                           
def sense():

    global watering_time

    global control 
    
    temperature = [] #list stores values of temperature
    
    humidity = [] #list stores values of humidity

    ET_S = [] #list stores values of hourly basis ET_station 

    ET_L = [] #list stores values of houely basis ET_local
    
    sumCnt = 0 #number of reading times

    while True:

        print("sumCnt : ", sumCnt)
            
        hum, temp = Read_Sensor()
        
        #store data in the list             
        humidity.append(hum)    
        temperature.append(temp)

        #lcd.clear()
        destroy()
        lcd.setCursor(0,0) # set cursor position

        x = '{:.2f}'.format(hum)
        y = '{:.2f}'.format(temp)

        lcd.message( 'H: ' + x + ' %\n' )   #display the humidity
        lcd.message( 'T: ' + y + ' C' )     #display the temperature        
                                    
        sumCnt += 1
            
        if sumCnt == 60:    # counter is 60 to get average of every hour
            
            sleep(2)
                
            avg_hum, avg_temp = get_Avg(humidity, temperature)
            print("Avg Humidity : ", avg_hum, "   Avg Temperature : ", avg_temp, '\n') 

            Date = (date.today()).strftime('%m/%d/%Y')    #get current date                
            Hour = (datetime.now().time()).strftime("%H") #get current hour
                
            #lcd.clear()
            destroy()
            lcd.setCursor(0,0) # set cursor position

            x =  '{:.2f}'.format(avg_hum)
            y =  '{:.2f}'.format(avg_temp)

            lcd.message( 'AVG H: ' + x + ' %\n' )# display average humidity
            lcd.message( 'AVG T: ' + y + ' C') # display the average temperature

            sleep(2)
                  
            #modify the date format  ex. 06/09/2020 -> 6/9/2020
            Date = Date.split('/')
            Date.insert(1,'/')
            Date.insert(3,'/')

            for i in range(len(Date)):
                if Date[i][0] == '0':
                    Date[i] = Date[i][1:]

            Date = ''.join(Date)

            #modify the hour format  ex. 03 -> 0300
            Hour = Hour + '00'
                          
            print("Current date is : ", Date, "   Current hour is : ", Hour, "    Current time is : ", datetime.now().time(), '\n' )
                               
            ETo, CIMIS_Hum, CIMIS_Temperature = CIMIS_data(Date, Hour)

            print("ETo : ",ETo, "    CIMIS_Hum : ", CIMIS_Hum, "    CIMIS_Temperature : ", CIMIS_Temperature, '\n')

            destroy()
            lcd.setCursor(0,0) # set cursor position

            lcd.message( 'CIMIS_H: ' + CIMIS_Hum + ' %\n' ) # display CIMIS humidity
            lcd.message( 'CIMIS_T: ' + CIMIS_Temperature + ' F') # display CIMIS temperature

            sleep(2)

            #convert string to float
            ETo = float(ETo)
            CIMIS_Hum = float(CIMIS_Hum)
            CIMIS_Temperature = float(CIMIS_Temperature)

            #convert F to C
            CIMIS_Temperature = (CIMIS_Temperature - 32) * (5/9)

            #calculate ET_station, watering_time, and ET_local
            ET_station, ET_local, watering_time  = watering(ETo, CIMIS_Hum, avg_hum, CIMIS_Temperature, avg_temp)
            
            #store data in the list to calculate the amount of water after n hours 
            ET_S.append(ET_station)
            ET_L.append(ET_local)
            
            print("ET_station : ", ET_station, " gallons/h", "    ET_local : ", ET_local, " gallons/h\n")

            print("Total ET_station water at current hour : ", sum(ET_S), '\n')

            print("Total ET_local water at current hour : ", sum(ET_L), '\n')
                          
            print("watering_time : ", watering_time, '\n')
                        
            destroy()
            lcd.setCursor(0,0) # set cursor position

            x =  '{:.2f}'.format(ET_local)
            y =  '{:.2f}'.format(ET_station)

            lcd.message( 'ET Local: ' + x + '\n') # display ET_local
            lcd.message( 'ET Station: ' + y ) # display ET_station

            sleep(2)

            destroy()
            lcd.setCursor(0,0) # set cursor position
            
            if ET_local < ET_station:
                print("Potential Water Saved\n")
                lcd.message( 'Potential Water\n')
                lcd.message( 'Saved')
                
            elif ET_local > ET_station:
                print("Additional Water Used\n")
                lcd.message( 'Additional Water\n')
                lcd.message( 'Used\n')
                
            else:
                print("Standard Usage\n")
                lcd.message( 'Standard Usage\n')
                                   
            sumCnt = 0  #reset number of reading times
                
            temperature.clear() #clear the temperature list
            humidity.clear() #clear the humidity list

            control = 1 # activate the watering mode

        sleep(60)  # sleep 60s to get values every minute

                                                            
PCF8574_address = 0x27 # I2C address of the PCF8574 chip.
PCF8574A_address = 0x3F # I2C address of the PCF8574A chip.
# Create PCF8574 GPIO adapter.
try:
    mcp = PCF8574_GPIO(PCF8574_address)
    
except:
    try:
        mcp = PCF8574_GPIO(PCF8574A_address)
    except:
        print ('I2C Address Error !')
        exit(1)
        
# Create LCD, passing in MCP GPIO adapter.
lcd = Adafruit_CharLCD(pin_rs=0, pin_e=2, pins_db=[4,5,6,7], GPIO=mcp)


if __name__ == '__main__':
    print ('Program is starting ... \n')

    mcp.output(3,1) #turn on LCD backlight
    lcd.begin(16,2) #set number of LCD lines and columns

    try:
                
        t1 = threading.Thread(target = irrigate)
        t1.start()
        
        t2 = threading.Thread(target = sense)
        t2.start()
                                               
    except KeyboardInterrupt:
        destroy()
        GPIO.cleanup()
        exit()  
