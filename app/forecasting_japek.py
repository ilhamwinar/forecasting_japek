import os
import mysql.connector
import logging
from datetime import datetime, timedelta
import numpy as np
import joblib
import xgboost
from decouple import config
import schedule
import time
import pickle
import ast

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",
    datefmt="%m/%d/%Y %H:%M:%S",
)


f = open('./app/config.txt', 'r')
api=f.read()
dictapi = ast.literal_eval(api)
#print(dictapi)
logging.info("PREPARING THE SERVICE PROGRAM FORECASTING")

##GET DATA FROM ENV####
host_server=dictapi["host_server"]
port_server=dictapi["port_server"]
user_db=dictapi["user_db"]
pass_db=dictapi["pass_db"]
name_db=dictapi["name_db"]
host_db=dictapi['host_db']
model=dictapi['model']


#def lalinperhari(path_parameter,up_or_down,table_cctv,count_forecasting)


def lalinperjam(path_parameter=str,up_or_down=str,table_cctv=str,count_forecasting=int):
    pred=[]
    pred_date=[]
    act=[]
    car_up=[]
    bus_up=[]
    truck_up=[]
    total_hour=[]
    # result_query.clear()
    logging.info("STARTING THE SERVICE PROGRAM FORECASTING LALIN PER JAM")

    try:
        cnx = mysql.connector.connect(user=user_db, 
                                    password=pass_db,
                                    host=host_db,
                                    database=name_db)
    except:
        logging.info("DATABASE NOT CONNECTED TO GET LALIN PER JAM")

    if cnx.is_connected():
        logging.info("DATABASE CONNECTED TO GET LALIN PER JAM")

    if table_cctv == 'CCTV_Traffic':
        if up_or_down == "up":
            sql0 ="select id,hour,car_up,bus_up,truck_up FROM (select id,hour,car_up,bus_up,truck_up FROM " 
            sql1="(select id,location, DATE(time) as date,hour(time) as hour, sum(car_up) as car_up, sum(`bus(s)_up`+ `bus(l)_up`) as bus_up, sum(`truck(s)_up` + `truck(m)_up` + `truck(l)_up` + `truck(xl)_up`) as truck_up,"
            sql2=" sum(car_down) as car_down, sum(`bus(s)_down`+ `bus(l)_down`) as bus_down, sum(`truck(s)_down` + `truck(m)_down` + `truck(l)_down` + `truck(xl)_down`) as truck_down"
            sql3=" from CCTV_Traffic where location = "+"'"+ path_parameter +"'"+" GROUP BY DATE,HOUR) as vehicle_hour"
            sql4=" where date = CURDATE()  ORDER BY hour) as vehiclehour where car_up IS NOT NULL and car_up != '0' ORDER BY id DESC limit 2;"
            sql=sql0+sql1+sql2+sql3+sql4
        if up_or_down == "down":
            sql0 ="select id,hour,car_down,bus_down,truck_down FROM (select id,hour,car_down,bus_down,truck_down FROM " 
            sql1="(select id,location, DATE(time) as date,hour(time) as hour, sum(car_down) as car_down, sum(`bus(s)_down`+ `bus(l)_down`) as bus_down, sum(`truck(s)_down` + `truck(m)_down` + `truck(l)_down` + `truck(xl)_down`) as truck_down"
            sql3=" from CCTV_Traffic where location = "+"'"+ path_parameter +"'"+" GROUP BY DATE,HOUR) as vehicle_hour"
            sql4=" where date = CURDATE() ORDER BY hour) as vehiclehour where car_down IS NOT NULL and car_down != '0' ORDER BY id DESC limit 2;"
            sql=sql0+sql1+sql3+sql4
        try:
            cursor = cnx.cursor()
            cursor.execute(sql)
            result_query = cursor.fetchall()

        except:
            logging.error("error QUERY TO GET LALIN PER JAM"+path_parameter+" Lajur "+up_or_down+ " DB: "+table_cctv)

    elif table_cctv == 'CCTV_Traffic_V2':
        # if up_or_down == "down":
        #     sql_up_v2="CALL CCTV_TRAFFIC_V2_HOUR_V2_DOWN('"+path_parameter+"');" 
        #logging.info("setelah if")
        logging.info(path_parameter)
        try:
            if up_or_down == "up":
                #logging.info("MASUK IF UP")
                cursor = cnx.cursor()
                cursor.callproc("CCTV_TRAFFIC_V2_HOUR_V2_UP",(path_parameter,))
            if up_or_down == "down":
                #logging.info("MASUK IF DOWN")
                cursor = cnx.cursor()
                cursor.callproc("CCTV_TRAFFIC_V2_HOUR_V2_DOWN",(path_parameter,))

            for result in cursor.stored_results():
                #logging.info(result)
                result_query = result.fetchall()
                #logging.info(result_query)
        except:
            logging.error("error QUERY TO GET LALIN PER JAM"+path_parameter+" Lajur "+up_or_down+ " DB: "+table_cctv)
    
    #GET INPUT MODEL
    try:
        act=np.array([[int(result_query[1][2]),int(result_query[1][3]),int(result_query[1][4])]])
    except:
        return None
    
    try:
        model = joblib.load("./app/xgb_japek_hour.dat")
    except:
        logging.error("CANNOT FORECAST WITH MODEL")

    #PREDICTING WITH LAST DATA ACTUAL AND LOOP FOR FORECASTING.
    for x in range(count_forecasting):
        if len(pred)==0:
            result = model.predict(act)
            pred.append(result)
            # logging.info(str(result))
            next_date = result_query[1][1] + 1
            if next_date == 25:
                next_date=1
            elif next_date == 26:
                next_date=2
            elif next_date == 27:
                next_date=3
            elif next_date == 28:
                next_date=4
            elif next_date == 29:
                next_date=5
            elif next_date == 30:
                next_date=6
            pred_date.append(next_date)
        elif len(pred)>0:
            i=int(x)-1
            act=pred[i]
            result = model.predict(act)
            pred.append(result)
            next_date = next_date + 1
            if next_date == 25:
                next_date=1
            elif next_date == 26:
                next_date=2
            elif next_date == 27:
                next_date=3
            elif next_date == 28:
                next_date=4
            elif next_date == 29:
                next_date=5
            elif next_date == 30:
                next_date=6
            pred_date.append(next_date)

    # print(pred)
    # print(pred_date)
    logging.info("SUCCESS FORECASTING "+path_parameter+" Lajur "+up_or_down )
    cursor.close()
    cnx.close()
    
    #APPENDING DATA CAR,BUS,TRUCK
    for i in range(count_forecasting):
        car_up.append(int(pred[i][0][0]))
        bus_up.append(int(pred[i][0][1]))
        truck_up.append(int(pred[i][0][2]))
        total_hour.append(car_up[i]+bus_up[i]+truck_up[i])
    
    #######car_up,bus_up,truck_up,total_hour,actual_last_hour_car,actual_last_hour_bus,actual_last_hour_truck, actual_now_car_up, actual_now_bus_up,actual_now_truck_up,hourbefore,prediksi_date
    return car_up,bus_up,truck_up,total_hour,(result_query[1][2]),int(result_query[1][3]),int(result_query[1][4]),int(result_query[0][2]),int(result_query[0][3]),int(result_query[0][4]),int(result_query[1][1]),pred_date

def vc_ratio_per_hour(cctvkm=str,up_or_down=str,table_cctv=str,count_forecasting=int):
    ####VARIABLE TANPA UP YA, HANYA NAMA PADAHAL BISA DIPAKE UNTUK DOWN.
    vc_ratio_pred=[]
    try:
        cnx = mysql.connector.connect(user=user_db, 
                                    password=pass_db,
                                    host=host_db,
                                    database=name_db)
    except:
        logging.info("DATABASE NOT CONNECTED TO GET VC RATIO HOUR")

    if cnx.is_connected():
        logging.info("DATABASE CONNECTED TO GET VC RATIO HOUR")

    sql= "select capacity from master_kapasitas_lajur where location = '" + cctvkm + "'"
    logging.info("path parameternya adalah: "+ cctvkm)
    try:
        cursor = cnx.cursor()
        cursor.execute(sql)
        result_query = cursor.fetchall()
    except:
        logging.error("error QUERY TO GET VC RATIO HOUR")

    car_up,bus_up,truck_up,total_hour,actual_last_hour_car,actual_last_hour_bus,actual_last_hour_truck, actual_now_car_up, actual_now_bus_up,actual_now_truck_up,hour_actual_before,pred_date=lalinperjam(cctvkm,up_or_down,table_cctv,count_forecasting)
    logging.info("SUCCESSED GET DATA LALIN PER JAM "+ cctvkm)


    smp_car_up=1
    smp_truck_up=2
    
    capacity=int(str((result_query[0])[0]))

    for i in range(count_forecasting-1):
        v_car_up=car_up[i]*smp_car_up
        v_bus_up=bus_up[i]*smp_truck_up
        v_truck_up=truck_up[i]*smp_truck_up
        v_total_up=v_car_up+v_bus_up+v_truck_up
        vc_ratio_up=round((v_total_up/capacity),2)
        vc_ratio_pred.append(vc_ratio_up) 
    
    v_car_actual=actual_last_hour_car*smp_car_up
    v_bus_actual=actual_last_hour_bus*smp_truck_up
    v_truck_actual=actual_last_hour_truck*smp_truck_up
    v_total_actual=v_car_actual+v_bus_actual+v_truck_actual
    
    vc_ratio_actual=round((v_total_actual/capacity),2)

    cnx.close()
    return vc_ratio_pred,vc_ratio_actual

def vc_ratio_per_day(cctvkm,count_forecasting):
    return 0

def forecast_vehicle_hour(insertdb=str,table_cctv=str,up_or_down=str,location=str,titikcctv=str, cctvkm=str, count_forecasting=int,delay=int):
    # """
    # insertdb = Database yang dituju, location = ruas cctv, titikcctv = KM47 misalnya, cctvkm = 200 misalnya titik meter, 
    # count forecating = jumlah forecasting kedepan, delay = delay waktu

    # """

    #car_up,bus_up,truck_up,total_hour,actual_last_hour_car,actual_last_hour_bus,actual_last_hour_truck, actual_now_car_up, actual_now_bus_up,actual_now_truck_up
    path_parameter=location+" "+titikcctv+" "+cctvkm
    #print(path_parameter)

    logging.info("CONNECTED TO RUAS "+path_parameter)

    try:
        car_up,bus_up,truck_up,total_hour,actual_last_hour_car,actual_last_hour_bus,actual_last_hour_truck, actual_now_car_up, actual_now_bus_up,actual_now_truck_up,hour_actual_before,pred_date=lalinperjam(path_parameter,up_or_down,table_cctv,count_forecasting)
        logging.info("SUCCESSED GET DATA LALIN PER JAM "+path_parameter)
    
    except:
        logging.info("FAILED GET DATA LALIN PER JAM CCTV NOT OK "+path_parameter)
        car_up=0
        bus_up=0
        truck_up=0
        total_hour=0
        actual_last_hour_car=0
        actual_last_hour_bus=0
        actual_last_hour_truck=0
        actual_now_car_up=0
        actual_now_bus_up=0
        actual_now_truck_up=0
        hour_actual_before=0
        pred_date=0
    
    try:
        vc_ratio_prediksi,vc_ratio_actual=vc_ratio_per_hour(path_parameter,up_or_down,table_cctv,10)
        logging.info("SUCESSED GET DATA VC RATIO RUAS "+path_parameter)
    except:
        vc_ratio_prediksi=[]
        vc_ratio_prediksi.append(0)
        vc_ratio_actual=0

    try:
        cnx = mysql.connector.connect(user=user_db, 
                                    password=pass_db,
                                    host=host_db,
                                    database=name_db)
    except:
        logging.info("DATABASE NOT CONNECTED TO "+path_parameter+" IN DB: "+ insertdb)

    if cnx.is_connected():
        logging.info("DATABASE CONNECTED TO "+path_parameter+" IN DB: "+ insertdb)
    
    time_update=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        # print(time_update)
        sql1 =  """ INSERT INTO {} (time_update, ruas, location, car_actual, bus_actual, truck_actual, car_pred, bus_pred, truck_pred,data_prediction,data_actual,vc_ratio_actual,vc_ratio_pred) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """.format(insertdb)
        
        total_actual_last_hour=actual_last_hour_car+actual_last_hour_bus+actual_last_hour_truck
        val = (time_update,location, path_parameter,actual_last_hour_car,actual_last_hour_bus,actual_last_hour_truck,car_up[0],bus_up[0],truck_up[0],total_hour[0],total_actual_last_hour,vc_ratio_actual,vc_ratio_prediksi[0]) 
        cursor = cnx.cursor()

        try: 
            cursor.execute(sql1, val)
            cnx.commit()
        
        except:
            cursor.rollback()
            logging.error("NOT INSERTED TO DATABASE TABLE "+insertdb+" LOCATION: "+path_parameter)
        logging.info("INSERTED TO DATABASE TABLE "+insertdb+" LOCATION: "+path_parameter)
    
    except:
        pass
        logging.error("NOT INSERTED TO DATABASE TABLE "+insertdb+" LOCATION: "+path_parameter)
        cnx.close()
      
    cnx.close()
    

def forecast_vehicle_day(insertdb=str,location=str,titikcctv=str, cctvkm=str, count_forecasting=int,delay=int):
    return 0

def hourly():
    # #KM15
    # forecast_vehicle_hour('prediction_hour_up','CCTV_Traffic','up','JAPEK',"KM15",'000',10,1)
    # forecast_vehicle_hour('prediction_hour_down','CCTV_Traffic','down','JAPEK',"KM15",'000',10,1)

    # #KM47
    forecast_vehicle_hour('prediction_hour_up','CCTV_Traffic','up','JAPEK',"KM47",'200',10,1)
    forecast_vehicle_hour('prediction_hour_down','CCTV_Traffic','down','JAPEK',"KM47",'200',10,1)

    # #KM50
    forecast_vehicle_hour('prediction_hour_up','CCTV_Traffic_V2','up','JAPEK','KM50','000',10,1)
    forecast_vehicle_hour('prediction_hour_down','CCTV_Traffic_V2','down','JAPEK','KM50','000',10,1)
    
    # #KM52
    forecast_vehicle_hour('prediction_hour_up','CCTV_Traffic_V2','up','JAPEK','KM52','000',10,1)
    forecast_vehicle_hour('prediction_hour_down','CCTV_Traffic_V2','down','JAPEK','KM52','000',10,1)

    # # #KM69
    forecast_vehicle_hour('prediction_hour_up','CCTV_Traffic_V2','up','JAPEK','KM69','000',10,1)
    forecast_vehicle_hour('prediction_hour_down','CCTV_Traffic_V2','down','JAPEK','KM69','000',10,1)

    #JAGORAWI
    forecast_vehicle_hour('prediction_hour_up','CCTV_Traffic_V2','up','JAGORAWI','KM46','000',10,1)
    forecast_vehicle_hour('prediction_hour_down','CCTV_Traffic_V2','down','JAGORAWI','KM46','000',10,1)

# def daily():    
#     forecast_vehicle_hour('prediction_day_down','CCTV_Traffic_V2','up','JAPEK','KM69','000',10,1)
#schedule.every(1).minutes.do(hourly)

schedule.every().day.at("00:01:05").do(hourly)
schedule.every().day.at("01:01:05").do(hourly)
schedule.every().day.at("02:01:05").do(hourly)
schedule.every().day.at("03:01:05").do(hourly)
schedule.every().day.at("04:01:05").do(hourly)
schedule.every().day.at("05:01:05").do(hourly)
schedule.every().day.at("06:01:05").do(hourly)
schedule.every().day.at("07:01:05").do(hourly)
schedule.every().day.at("08:01:05").do(hourly)
schedule.every().day.at("09:01:05").do(hourly)
schedule.every().day.at("10:01:05").do(hourly)
schedule.every().day.at("11:01:05").do(hourly)
schedule.every().day.at("12:01:05").do(hourly)
schedule.every().day.at("13:01:05").do(hourly)
schedule.every().day.at("14:01:05").do(hourly)
schedule.every().day.at("15:01:05").do(hourly)
schedule.every().day.at("16:01:05").do(hourly)
schedule.every().day.at("17:01:05").do(hourly)
schedule.every().day.at("18:01:05").do(hourly)
schedule.every().day.at("19:01:05").do(hourly)
schedule.every().day.at("20:01:05").do(hourly)
schedule.every().day.at("21:01:05").do(hourly)
schedule.every().day.at("22:01:05").do(hourly)
schedule.every().day.at("23:01:05").do(hourly)

# schedule.every(1).minutes.do(hourly)
# schedule.every(1).minutes.do(hourly1)

while True:
    schedule.run_pending()
    #logging.info("wait next job")
    time.sleep(1)


