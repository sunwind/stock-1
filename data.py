# -*- coding:utf-8 -*-  
from pymongo import MongoClient
from stockclass import Stock
from datetime import date, timedelta, datetime
from functools import partial
from multiprocessing.dummy import Pool as ThreadPool
import tushare as ts
import json, logging
from pandas import Series
def fetchDataOneThread(prefix, startday, endday):
    data = []
    for index in range(pow(10,(6-len(prefix)))):
        suffix = str(index).zfill(6-len(prefix))
        stockId = prefix + suffix
        try:    
            result = ts.get_hist_data(stockId, start=startday.isoformat(),end=endday.isoformat())
            stock = Stock()
            stock.id = stockId
            stock.dates = result.index.tolist()
            stock.openPrices = result.open.values.tolist()
            stock.closePrices = result.close.values.tolist()
            stock.v_ma5 = result.v_ma5.values.tolist()
            stock.volume = result.volume.tolist()
            stock.PChange()
            data.append(stock)
        except Exception, e:
            print e
            if(str(e).find("list index out of range") > -1):
                logging.warning(str(e))
            print stockId + " is not a valid stock.\n"
    return data

#ǰ��Ȩ
def fetchDataOneThreadwithFQ(prefix, startday, endday):
    data = []
    for index in range(pow(10,(6-len(prefix)))):
        suffix = str(index).zfill(6-len(prefix))
        stockId = prefix + suffix
        try:    
            result = ts.get_h_data(stockId, start=startday.isoformat(),end=endday.isoformat())
            stock = Stock()
            stock.id = stockId
            dates = result.index.tolist()
            for day in dates:
                stock.dates.append(day.date().isoformat())
            stock.openPrices = result.open.values.tolist()
            stock.closePrices = result.close.values.tolist()
            stock.volume = result.volume.tolist()
            stock.calc_v_ma5()
            stock.PChange()
            data.append(stock)
        except Exception, e:
            print e
            if(str(e).find("list index out of range") > -1):
                logging.warning(str(e))
            print stockId + " is not a valid stock.\n"
    return data

def fetchToday(stocks):
    today = date.today()
    stocksnow = ts.get_today_all()
    codes = stocksnow.code.tolist()
    for stock in stocks:
        stockidx = -1
        for codeidx, code in enumerate(codes):
            if(stock.id == code):
                stockidx = codeidx
                break
        if(stockidx > -1):
            stock.name = stocksnow.name.tolist()[stockidx]
            if(len(stock.dates) - 1 < 0):
                continue
            if(today.isoformat() != stock.dates[len(stock.dates) - 1]):
                if(len(stock.closePrices) - 1 < 0):
                    continue
                stock.dates.append(today)
                stock.openPrices.append(stocksnow.open.tolist()[stockidx])
                stock.closePrices.append(stocksnow.trade.tolist()[stockidx])
                if(stocksnow.open.tolist()[stockidx] == 0.0):
                    stock.changePrices.append(0.0)
                else:
                    stock.changePrices.append((stocksnow.trade.tolist()[stockidx] - stocksnow.open.tolist()[stockidx])/stocksnow.open.tolist()[stockidx])
                stock.volume.append(stocksnow.volume.tolist()[stockidx])
                idx = stock.indexof(today)
                if(idx >= 4):
                    stock.v_ma5.append((stock.volume[idx] + stock.volume[idx - 1] + stock.volume[idx - 2] + stock.volume[idx - 3] + stock.volume[idx - 4])/5)
                else:
                    total = 0
                    i = 0
                    while(i<=idx):
                        total += stock.volume[idx - i]
                        i += 1
                    stock.v_ma5.append(total/(idx + 1))
                    
def fetchData(dataPrefix, startday, endday):
    data = []
    arg = []
    pool = ThreadPool(len(dataPrefix))
    partial_fetchDataOneThreadwithFQ = partial(fetchDataOneThreadwithFQ, startday=startday, endday=endday)
    #results = pool.map(fetchDataOneThread, arg)
    results = pool.map(partial_fetchDataOneThreadwithFQ, dataPrefix)
    pool.close()
    pool.join()
    for result in results:
        data.extend(result)
    #fetchToday(data)
    return data

def storeData(prefix, startday, endday):
    data = []
    client =MongoClient('mongodb://localhost:27017/')
    database = client["stock"]
    newlastday = None
    newbeginday = None
    for index in range(pow(10,(6-len(prefix)))):
        suffix = str(index).zfill(6-len(prefix))
        stockId = prefix + suffix
        try:    
            results = ts.get_h_data(stockId, start=startday.isoformat(),end=endday.isoformat())
            results["stockId"] = Series([stockId for x in range(len(results.index.tolist()))], index = results.index)
            results["date"] = Series([x.date().isoformat() for x in results.index.tolist()], index = results.index)
            ticks = database.ticks
            if(ticks == None):
                database.create_collection("ticks")
                ticks = database.ticks
            #tick = ticks.find_one({"stockId": stockId, "date":{'$gte': startday.isoformat(),'$lte': endday.isoformat()}})
            #if(tick == None):
            ticks.insert(json.loads(results.to_json(orient='records')))
            dates = results.index.tolist()
            if(newlastday == None or newlastday < dates[0].date()):
                newlastday = dates[0].date()
            if(newbeginday == None or newbeginday < dates[len(dates) - 1].date()):
                newbeginday = dates[len(dates) - 1].date()
        except Exception, e:
            print e
            if(str(e).find("list index out of range") > -1):
                logging.warning(str(e))
            print stockId + " is not a valid stock.\n"
    profilecollections = database.profile
    profile = profilecollections.find_one()
    if(newlastday != None):
        if(profile != None):
            profilecollections.update_one({'_id': profile['_id']}, {'$set': {'lastupdateday': newlastday.isoformat()}})
        else:
            profilecollections.insert_one({'lastupdateday': newlastday.isoformat()})
    profile = profilecollections.find_one()
    if(newbeginday != None):
        if(profile != None):
            profilecollections.update_one({'_id': profile['_id']}, {'$set': {'beginupdateday': newbeginday.isoformat()}})
        else:
            profilecollections.insert_one({'beginupdateday': newbeginday.isoformat()})
    client.close()

def getDataFromMongoOnethread(prefix, startday, endday):
    data = []
    client =MongoClient('mongodb://localhost:27017/')
    database = client["stock"]
    try:    
        ticks = database.ticks
        if(ticks != None):
            prefixstart = int(prefix)*pow(10,(6-len(prefix)))
            prefixend = prefixstart + pow(10,(6-len(prefix))) - 1
            resultgroups = ticks.group(["stockId"], {"stockId":{'$gte': str(prefixstart).zfill(6),'$lte': str(prefixend).zfill(6) }, "date":{'$gte': startday.isoformat(),'$lte': endday.isoformat()}},
                                       {'list': []},'function(obj, prev) {prev.list.push(obj)}') # reducer)
            for resultlists in resultgroups:
                if(len(resultlists) > 0):
                    results = resultlists['list']
                    results.sort(key=lambda x:x['date'])
                    stock = Stock()
                    stock.id = results[0]["stockId"]
                    for result in results:
                        stock.dates.append(result['date'])
                        stock.openPrices.append(result['open'])
                        stock.closePrices.append(result['close'])
                        stock.volume.append(result['volume'])
                    stock.calc_v_ma5()
                    stock.PChange()
                    data.append(stock)
    except Exception, e:
        print e
        logging.warning(str(e))
    client.close()
    return data

def fetchData_mongo(dataPrefix, startday, endday):
    
    client =MongoClient('mongodb://localhost:27017/')
    db = client["stock"]
    profilecollections = db.profile
    if(profilecollections == None):
        db.create_collection("profile")
        profilecollections = db.profile
    profile = profilecollections.find_one()
    client.close()
    fetch_endday = endday
    fetch_starday = startday
    if(profile != None):
        beginday = datetime.strptime(profile['beginupdateday'], '%Y-%m-%d').date()
        lastday = datetime.strptime(profile['lastupdateday'], '%Y-%m-%d').date()
        #if(fetch_endday >= beginday):
        #    fetch_endday = beginday - timedelta(days=1)
        if(fetch_starday <= lastday):
            fetch_starday = lastday + timedelta(days=1)
    if(fetch_starday <= fetch_endday):
        partial_storeData = partial(storeData, startday=fetch_starday, endday=fetch_endday)
        pool = ThreadPool(len(dataPrefix))
        pool.map(partial_storeData, dataPrefix)
        pool.close()
        pool.join()
        
    
    data = []
    pool = ThreadPool(len(dataPrefix))
    partial_getDataFromMongoOnethread = partial(getDataFromMongoOnethread, startday=startday, endday=endday)
    results = pool.map(partial_getDataFromMongoOnethread, dataPrefix)
    pool.close()
    pool.join()
    for result in results:
        data.extend(result)
    
    #fetchToday(data)

    return data
'''
prefixes = ['6000','6001','6002','6003','6004','6005','6006','6007','6008','6009', '6010', '6011', '6012', '6013', '6014', '6015', '6016', '6017',  '6018', '6019', '6030', '6031', '6032', '6033', '6034', '6035', '6036', '6037', '6038', '6039', '0020','0021','0022','0023','0024','0025','0026','0027','0028','0029']
#prefixes = ['60030']

startday = datetime.strptime("2010-01-01", '%Y-%m-%d').date()
endday = datetime.strptime("2014-05-28", '%Y-%m-%d').date()
stocks = fetchData_mongo(prefixes, startday, endday)
'''