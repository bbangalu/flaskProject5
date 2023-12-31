from flask import Flask, render_template, request, jsonify
import requests
import xml.etree.ElementTree as ET
import logging
from functools import lru_cache

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG)

ENDPOINT = "http://openapi.airport.co.kr/service/rest/FlightStatusList/getFlightStatusList"
SERVICE_KEY = "3jkDYzA2uD6s50OH4zqE/NRd7uXuypkyG0gG7Rq550Dnn4nQYBcUpRKVMELmOpA3vh5vZ4n+kozC0gXkkDcWHg=="
AIRPORT_CODES = [
    {"code": "GMP", "name": "김포"},
    {"code": "CJU", "name": "제주"},
    {"code": "PUS", "name": "부산"},
    {"code": "MWX", "name": "무안"},
    {"code": "YNY", "name": "양양"},
    {"code": "CJJ", "name": "청주"},
    {"code": "TAE", "name": "대구"},
    {"code": "WJU", "name": "원주"},
    {"code": "KPO", "name": "포항"},
    {"code": "USN", "name": "울산"},
    {"code": "HIN", "name": "사천"},
    {"code": "KUV", "name": "군산"},
    {"code": "KWJ", "name": "광주"},
    {"code": "RSU", "name": "여수"},
]

@app.route('/', methods=['GET', 'POST'])
def index():
    selected_airport = request.args.get('airport_code', "USN")
    if request.method == 'POST':
        selected_airport = request.form.get('airport_code', "USN")

    departures, arrivals = fetch_flight_info(selected_airport)
    mark_flights_in_air(departures, arrivals, selected_airport)
    return render_template('index.html', departures=departures, arrivals=arrivals, AIRPORT_CODES=AIRPORT_CODES, selected_airport=selected_airport)

@app.route('/fetch_info', methods=['GET'])
def fetch_info():
    airport_code = request.args.get('airport_code', "USN")
    departures, arrivals = fetch_flight_info(airport_code)
    mark_flights_in_air(departures, arrivals, airport_code)
    return jsonify({
        "departures": departures,
        "arrivals": arrivals
    })


def get_airport_code_from_name(airport_name):
    airport_name_to_code = {
        '서울/김포': 'GMP',
        '부산/김해': 'PUS',
        '제주': 'CJU',
        '무안': 'MWX',
        '양양': 'YNY',
        '청주': 'CJJ',
        '대구': 'TAE',
        '원주': 'WJU',
        '포항/포항경주': 'KPO',
        '울산': 'USN',
        '진주/사천': 'HIN',
        '군산': 'KUV',
        '광주': 'KWJ',
        '여수': 'RSU',
    }
    return airport_name_to_code.get(airport_name)

@lru_cache(maxsize=32)  # Using cache to store results
def fetch_flight_info(airport_code="USN"):
    params = {
        "ServiceKey": SERVICE_KEY,
        "schAirCode": airport_code,
        "schLineType": "D",
        "numOfRows": 1000
    }

    response = requests.get(ENDPOINT, params=params)
    departures = []
    arrivals = []

    if response.status_code == 200:
        root = ET.fromstring(response.content)
        for item in root.findall(".//item"):
            flight_data = {
                "airFln": item.find("airFln").text if item.find("airFln") is not None else "",
                "airlineKorean": item.find("airlineKorean").text if item.find("airlineKorean") is not None else "",
                "boardingKor": item.find("boardingKor").text if item.find("boardingKor") is not None else "",
                "arrivedKor": item.find("arrivedKor").text if item.find("arrivedKor") is not None else "",
                "std": item.find("std").text if item.find("std") is not None else "",
                "etd": item.find("etd").text if item.find("etd") is not None else "-",
                "rmkKor": item.find("rmkKor").text if item.find("rmkKor") is not None else "",
                "gate": item.find("gate").text if item.find("gate") is not None else "-",
                "flying": ""  # 비행 중 상태를 저장할 새로운 필드
            }

            if item.find("io").text == "O":  # 출발
                departures.append(flight_data)
            else:  # 도착
                arrivals.append(flight_data)
    else:
        logging.error(f"API request failed with status code {response.status_code}. Response: {response.text}")

    return departures, arrivals

def mark_flights_in_air(departures, arrivals, selected_airport):
    # Fetch flight info for all airports in advance
    all_flights_info = {airport["code"]: fetch_flight_info(airport["code"]) for airport in AIRPORT_CODES}


    # Handle arrivals
    for arrival in arrivals:
        origin_airport_name = arrival['boardingKor']
        origin_airport_code = get_airport_code_from_name(origin_airport_name)
        all_departures_for_origin = all_flights_info[origin_airport_code][0]  # Only need departure info


        matching_departure = next(
            (departure for departure in all_departures_for_origin if departure['airFln'] == arrival['airFln']), None)

        if matching_departure:
            arrival['flying'] = matching_departure['rmkKor']
            if arrival['flying'] == "출발":
                arrival['flying2'] = "비행 중"
                arrival['flight_link'] = f"https://www.flightradar24.com/{arrival['airFln']}"
            else:
                arrival['flying2'] = "출발 전"
        else:
            arrival['flying2'] = '정보 없음'

        # flying2 값 설정
        if not arrival['rmkKor'] and arrival['flying'] == "출발":
            arrival['flying2'] = "비행 중"
        elif not arrival['rmkKor']:
            arrival['flying2'] = "출발 전"
        elif arrival['rmkKor'] == "도착":
            arrival['flying2'] = "비행 종료"

    # 출발 정보에 대한 처리
    for departure in departures:
        destination_airport_name = departure['arrivedKor']
        destination_airport_code = get_airport_code_from_name(destination_airport_name)
        all_arrivals_for_destination = all_flights_info[destination_airport_code][1]  # Only need arrival info

        matching_arrival = next(
            (arrival for arrival in all_arrivals_for_destination if arrival['airFln'] == departure['airFln']), None)

        if matching_arrival:
            departure['flying'] = matching_arrival['rmkKor']

        # flying2 값 설정
        if departure['rmkKor'] == "출발" and departure['flying'] == "도착":
            departure['flying2'] = "비행 종료"
        elif departure['rmkKor'] == "출발" and departure['flying'] != "도착":
            departure['flying2'] = "비행 중"
            departure['flight_link'] = f"https://www.flightradar24.com/{departure['airFln']}"  # 링크 추가
        elif departure['rmkKor'] != "출발":
            departure['flying2'] = "출발 전"


if __name__ == '__main__':
    app.run(debug=True)