import re
import json
import os


# Đường dẫn đến thư mục data (Giả định cấu trúc dự án: src/tools/tour_tools.py và data/ nằm cùng cấp cha)
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')

def _load_json(filename: str):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def search_attractions(args_str: str) -> str:
    city_match = re.search(r'city=[\'"]([^\'"]+)[\'"]', args_str)
    tags_match = re.search(r'tags=[\'"]([^\'"]+)[\'"]', args_str)
    
    city = city_match.group(1).capitalize() if city_match else ""
    # Nếu tags là chuỗi "cultural,accessible", tách nó ra
    tags = tags_match.group(1).split(",") if tags_match else []

    spots_db = _load_json('spots.json')
    if spots_db is None or city not in spots_db:
        return f"ERROR_NO_DATA: Không có dữ liệu địa điểm cho {city}."
    
    city_spots = spots_db.get(city, [])
    results = [s['name'] for s in city_spots if any(t in s['tags'] for t in tags)]
    
    if not results:
        return f"Không tìm thấy địa điểm phù hợp với tags {tags} tại {city}."
    return f"Các điểm tham quan tại {city}: {', '.join(results)}"

def check_weather_forecast(args_str: str) -> str:
    city_match = re.search(r'city=["\']([^"\']+)["\']', args_str)
    city = city_match.group(1).capitalize() if city_match else "DaNang"

    weather = _load_json('weather.json')
    if weather is None or city not in weather:
        return f"ERROR_NO_DATA: Thời tiết cho {city} không khả dụng."
    
    data = weather.get(city, {}).get("tomorrow", {})
    return f"Thời tiết {city} ngày mai: {data.get('condition', 'N/A')}, nhiệt độ {data.get('temp', 'N/A')}°C."

def calculate_tour_budget(args_str: str) -> str:
    pax_match = re.search(r'pax=(\d+)', args_str)
    car_match = re.search(r'car=["\']?([^"\']+)["\']?', args_str)
    city_match = re.search(r'city=["\']?([^"\']+)["\']?', args_str)
    
    pax = int(pax_match.group(1)) if pax_match else 6
    car_type = car_match.group(1) if car_match else "7_seater"
    city = city_match.group(1).capitalize() if city_match else "DaNang"
    
    cars_db = _load_json('cars.json')
    if cars_db is None or city not in cars_db:
        return f"ERROR_NO_DATA: Không tìm thấy thông tin xe tại {city}."
        
    city_cars = cars_db.get(city, [])
    car_info = next((c for c in city_cars if c['size'] == car_type), None)
    
    if not car_info:
        return f"Không có thông tin xe {car_type} tại {city}."
        
    car_cost = car_info['price']
    ticket_cost = pax * 80000
    total = car_cost + ticket_cost
    
    return f"Tại {city}: Xe {car_type} giá {car_cost:,} VNĐ. Vé ({pax} khách): {ticket_cost:,} VNĐ. Tổng: {total:,} VNĐ."