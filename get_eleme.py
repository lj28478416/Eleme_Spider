import requests
from jsonpath import jsonpath
import json
import geohash
import csv
import urllib3
import random
import time
import gevent
import pymongo
# from gevent import monkey
from multiprocessing.dummy import Pool
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# monkey.patch_all()
class ElemeSpider:
    def __init__(self,city_name,area_name):
        self.list_limit = 24
        self.city_name = city_name
        self.area_name = area_name
        self.num = 0
        self.client = pymongo.MongoClient('0.0.0.0', 27017)
        self.collection = self.client.eleme.eleme_ba
        self.headers={
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'cookie': 'ubt_ssid=3hzaooizvgnxobbzotcl7gnbs4kuq59f_2018-07-07; _utrace=d355d578eb4c6baad96c4a5baedb8b4e_2018-07-07; eleme__ele_me=2adde2bd36dd0eb85c7755d4909a26d2%3A07847e106501d1495cebea228f58dc2142f33684; track_id=1531530549|e19c3b256abbfbcb30e3e8bfb28fc057ed9b16ce052f4b0093|88cc85bb5375566f321ee59328ad09dc; USERID=3327435; SID=KU1PQykxMgEYeghl8ecH09WsCaq58irxQEYQ',
            'referer': 'https://www.ele.me/home/',
            'user-agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.117 Safari/537.36',
            'x-shard': 'loc=121.395555,31.24984'
        }
        self.areas_params = {
            'extras[]': 'count',
            'geohash': None,
            'keyword': self.area_name,
            'limit': '20',
            'type': 'nearby'
        }
        self.list_params = {
            'extras[]': 'activities',
            'geohash': None,
            'latitude': None,
            'limit': str(self.list_limit),
            'longitude': None,
            'restaurant_category_ids[]': '245',
            'offset': '0',
            'terminal': 'web'
        }
    def get_cities(self):
        cities_url = 'https://www.ele.me/restapi/shopping/v1/cities'
        response = requests.get(cities_url,headers=self.headers,verify=False).json()
        cities_list = response.values()
        cities_geo_list = []
        for cities_first_word in cities_list:
            for cities in cities_first_word:
                item={}
                item['city_name'] = cities['name']
                item['city_latitude'] = cities['latitude']
                item['city_longitude'] = cities['longitude']
                cities_geo_list.append(item)
        return cities_geo_list
    def send_address(self):
        for city_info in self.get_cities():
            if self.city_name == city_info['city_name']:
                break
        else:
            print('城市名错误')
            return
        city_geohash = geohash.encode(float(city_info['city_latitude']),float(city_info['city_longitude']))
        self.areas_params['geohash'] = city_geohash
        areas_url = 'https://www.ele.me/restapi/v2/pois?'
        areas_info = requests.get(areas_url,params=self.areas_params,headers=self.headers,verify=False).json()
        areas_list = []
        for areas in areas_info:
            item={}
            item['area_name'] = areas['name']
            item['area_latitude'] = areas['latitude']
            item['area_longitude'] = areas['longitude']
            item['area_geohash'] = geohash.encode(float(areas['latitude']),float(areas['longitude']))
            areas_list.append(item)
        return areas_list
    def get_restaurant(self):
        restaurant_url = 'https://www.ele.me/restapi/shopping/restaurants?'
        pool = Pool(50)
        for i in self.send_address():
            self.list_params['geohash'] = i['area_geohash']
            self.list_params['latitude'] = i['area_latitude']
            self.list_params['longitude'] = i['area_longitude']
            self.list_params['offset'] = 0
            # m = []
            while True:
                restaurant_onepage = requests.get(restaurant_url,params=self.list_params,headers=self.headers,verify=False).json()
                self.list_params['offset'] = str(int(self.list_params['offset']) + self.list_limit)
                if len(restaurant_onepage) == 0:
                    break
                pool.map(self.get_restaurant_detail,restaurant_onepage)
                # for j in restaurant_onepage:
                #     time.sleep(random.random())
                #     self.get_restaurant_detail(j)
        pool.close()
        pool.join()
        print('over')
    def get_restaurant_detail(self,j):
        restaurant_dict = {}
        self.num += 1
        restaurant_dict["_id"] = self.num
        print(self.num)
        restaurant_dict['店名'] = jsonpath(j, '$..name')[0]
        print(restaurant_dict['店名'])
        j_url = 'https://www.ele.me/restapi/ugc/v1/restaurants/' + str(jsonpath(j, '$..id')[0]) + '/rating_scores?'
        j_params = {
            'latitude': jsonpath(j, "$..latitude"),
            'longitude': jsonpath(j, "$..longitude")
        }
        while True:
            try:
                j_response = requests.get(j_url, params=j_params, headers=self.headers,verify=False).json()
                print(restaurant_dict['店名']+'success')
                break
            except ConnectionResetError as e:
                print(restaurant_dict['店名'] + 'error')
                continue
        if len(j_response) == 0:
            return
        restaurant_dict['好评率'] = str(jsonpath(j_response, '$..positive_rating')[0] * 100) + '%' if jsonpath(j_response, '$..positive_rating')[0] else '0'
        restaurant_dict['最近订单数'] = jsonpath(j, '$..recent_order_num')[0] if jsonpath(j, '$..recent_order_num')[0] else '0'
        restaurant_dict['超过附近商家百分比'] = str(jsonpath(j_response, '$..compare_rating')[0] * 100)[:5] + '%' if jsonpath(j_response, '$..compare_rating')[0] else '0'
        restaurant_dict['菜品评价(5满分)'] = jsonpath(j_response, '$..food_score')[0] if jsonpath(j_response, '$..food_score')[0] else '0'
        restaurant_dict['服务态度评价(5满分)'] = jsonpath(j_response, '$..service_score')[0] if jsonpath(j_response, '$..service_score')[0] else '0'
        restaurant_dict['综合评价星级(5满分)'] = jsonpath(j_response, '$..star_level')[0] if jsonpath(j_response, '$..star_level')[0] else '0'
        restaurant_dict['店铺id'] = jsonpath(j_response, '$..restaurant_id')[0] if jsonpath(j_response, '$..restaurant_id') else '0'
        restaurant_dict['地址'] = jsonpath(j, "$..address")[0] if jsonpath(j, "$..address")[0] else '无'
        restaurant_dict['商品评价页'] = 'https://www.ele.me/shop/' + str(jsonpath(j, '$..id')[0]) + '/rate' if jsonpath(j, '$..id')[0] else '无'
        self.collection.insert(restaurant_dict)
        # print(restaurant_dict)
        # print(restaurant_dict["_id"])
    #     self.save_info(restaurant_dict)
    # def save_info(self,restaurant_dict):
    #     pass
        # csv_header = restaurant_list[0].keys()
        # csv_data = [restaurant_info.values() for restaurant_info in restaurant_list]
        # with open(self.city_name + '---' + self.area_name + "---" + area_name +'.csv', 'w', encoding='utf-8', newline='') as f:
        #     csv_writer = csv.writer(f)
        #     csv_writer.writerow(csv_header)
        #     csv_writer.writerows(csv_data)
        # print("写入一页")
    def main(self):
        try:
            self.get_restaurant()
        except json.decoder.JSONDecodeError as f:
            print('ip被封')
            return
if __name__ == '__main__':
    # city_name = input('请输入城市名(不加市):')
    # area_name = input('请输入区域名:')
    spider = ElemeSpider('深圳','宝安')
    spider.main()
