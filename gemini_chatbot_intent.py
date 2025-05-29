import google.generativeai as genai
import json
import requests
from datetime import datetime, timedelta

genai.configure(api_key="AIzaSyB8d5o2veAopoa5FlcVxKqm3z8LNkP19Zk")
model = genai.GenerativeModel('models/gemini-2.0-flash')
chat = model.start_chat()

def extract_important_info(url, html_content, city=None):
    """Extract important information based on API type"""
    if "nghiphep/history" in url.lower():  
        return {
            "type": "link",
            "url": url,
            "title": "📋 Xem lịch sử nghỉ phép",
            "message": 
                """📊 Tại trang lịch sử nghỉ phép, bạn sẽ thấy:
- Danh sách tất cả đơn nghỉ phép đã gửi
- Thời gian và số ngày nghỉ của từng đơn
- Trạng thái phê duyệt (Đã duyệt/Đang chờ/Từ chối)
- Người phê duyệt và thời gian phê duyệt
                """
        }
 
    elif "project/progress" in url:  
        try:
            data = json.loads(html_content)
            return f"""
📊 Tên dự án: {data.get('project_name', 'N/A')}
📈 Tiến độ: {data.get('progress', '0')}%
⏰ Deadline: {data.get('deadline', 'N/A')}
📌 Trạng thái: {data.get('status', 'N/A')}
""".strip()
        except:
            return html_content
            
    elif "salary" in url:  
        try:
            data = json.loads(html_content)
            return f"""
💰 Lương cơ bản: {int(data.get('base_salary', 0)):,} VND
🎁 Thưởng: {int(data.get('bonus', 0)):,} VND
💵 Tổng thu nhập: {int(data.get('total', 0)):,} VND
📅 Kỳ lương: {data.get('period', 'N/A')}
""".strip()
        except:
            return html_content
    
    return html_content

def call_real_api(api_url, user_input=None):
    try:
        response = requests.get(api_url, timeout=5)
        if response.status_code == 200:
            return extract_important_info(api_url, response.text)
        else:
            return f"❌ Lỗi {response.status_code}: {response.text}"
    except Exception as e:
        return f"❌ Lỗi khi gọi API: {str(e)}"

def get_response(prompt):
    try:
        response = chat.send_message(prompt)
        # Return empty string instead of None on no response text
        return response.text.strip() if response.text else ""
    except Exception as e:
        print(f"Lỗi khi gọi Gemini: {str(e)}")
        # Return a predefined error response or empty string on error
        return "Error: Unable to get response from AI."

def clean_response(response):
    if not response:
        return "" # Ensure we return empty string if input is None or empty
    response = response.strip()
    if response.startswith('```') and response.endswith('```'):
        response = response[3:-3]
    if response.lower().startswith('json'):
        response = response[4:]
    return response.strip()

def get_working_hours(date):
    """
    Trả về thời gian làm việc cho một ngày cụ thể
    Returns: (start_time, end_time) hoặc None nếu là cuối tuần
    """
    if date.weekday() >= 5:  
        return None
        
    morning_start = datetime.combine(date.date(), datetime.strptime("08:30", "%H:%M").time())
    morning_end = datetime.combine(date.date(), datetime.strptime("12:00", "%H:%M").time())
    
    afternoon_start = datetime.combine(date.date(), datetime.strptime("13:30", "%H:%M").time())
    afternoon_end = datetime.combine(date.date(), datetime.strptime("17:30", "%H:%M").time())
    
    return {
        "morning": (morning_start, morning_end),
        "afternoon": (afternoon_start, afternoon_end)
    }

def calculate_leave_hours(from_date, to_date):
    """
    Tính số giờ nghỉ dựa trên thời gian làm việc
    """
    if not from_date or not to_date:
        return 0
        
    try:
        start = datetime.strptime(from_date, "%m %d %Y %H:%M")
        end = datetime.strptime(to_date, "%m %d %Y %H:%M")
        
        if end < start:
            return 0
            
        total_hours = 0
        current = start
        
        while current.date() <= end.date():
            working_hours = get_working_hours(current)
            
            if working_hours:
                morning_start, morning_end = working_hours["morning"]
                afternoon_start, afternoon_end = working_hours["afternoon"]
                
                if current.date() == start.date():
                    morning_start = max(morning_start, start)
                if current.date() == end.date():
                    morning_end = min(morning_end, end)
                    
                if morning_start < morning_end:
                    total_hours += (morning_end - morning_start).total_seconds() / 3600
                
                if current.date() == start.date():
                    afternoon_start = max(afternoon_start, start)
                if current.date() == end.date():
                    afternoon_end = min(afternoon_end, end)
                    
                if afternoon_start < afternoon_end:
                    total_hours += (afternoon_end - afternoon_start).total_seconds() / 3600
            
            current += timedelta(days=1)
            
        return int(round(total_hours))
    except Exception as e:
        print(f"Error calculating leave hours: {str(e)}")
        return 0

def export_payslip(month):
    """
    Xuất file lương theo tháng
    """
    try:
        url = f"https://mbi.sapotacorp.vn/api/UserAPI/OutputExcelPayslip"
        headers = {
            "accept": "application/json, text/plain, */*",
            "authorization": "michael##Hamia*10124##4",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "referer": "https://mbi.sapotacorp.vn/User/Payslip"
        }
        params = {
            "month": f"{month}-01T00:00:00"
        }
        response = requests.get(url, params=params, headers=headers)
        
        if response.status_code == 200:
            # Assume 200 OK means the file generation request was successful on the server
            # Return success=True and the response content/text for potential debugging if needed
            return {"success": True, "data": response.content, "message": response.text}
        else:
            # Non-200 status code indicates an error from the API
            return {"success": False, "message": f"Lỗi khi gọi API xuất file: {response.status_code} - {response.text}"}
            
    except Exception as e:
        # Handle connection errors or other exceptions
        return {"success": False, "message": f"Lỗi kết nối hoặc xử lý khi gọi API: {str(e)}"}

def detect_api_intent(user_input):
    current_date = datetime.now()
    # Calculate next day and next Monday/Friday for examples
    next_day = current_date + timedelta(days=1)
    # Find the next Monday and Friday
    days_until_monday = (0 - current_date.weekday() + 7) % 7
    next_monday = current_date + timedelta(days=days_until_monday)
    if next_monday.date() == current_date.date(): # If today is Monday, find next Monday
        next_monday += timedelta(days=7)
    
    days_until_friday = (4 - current_date.weekday() + 7) % 7
    next_friday = current_date + timedelta(days=days_until_friday)
    if next_friday.date() == current_date.date(): # If today is Friday, find next Friday
        next_friday += timedelta(days=7)
        
    prompt = f"""
Bạn là trợ lý AI. Phân tích yêu cầu của người dùng và xác định intent phù hợp.

Thông tin thời gian làm việc:
- Làm việc từ thứ 2 đến thứ 6
- Buổi sáng: 8:30 - 12:00
- Buổi chiều: 13:30 - 17:30
- Không làm việc thứ 7 và chủ nhật

Lưu ý quan trọng về xử lý ngày tháng:
- LUÔN LUÔN sử dụng "Ngày hiện tại là: {current_date.strftime('%m %d %Y %H:%M')}" làm mốc thời gian để suy luận các mốc thời gian tương đối như "hôm nay", "mai", "tuần sau", "thứ 2", v.v.
- Định dạng ngày giờ trả về phải là: "MM DD YYYY HH:mm" (ví dụ: "05 27 2024 08:30")

Cách xử lý thời gian:
1. Khi chỉ có ngày (ví dụ: "mai", "thứ 2"):
   - Nếu không chỉ định buổi → mặc định là cả ngày (8:30-17:30)
   - Nếu chỉ định buổi sáng → 8:30-12:00
   - Nếu chỉ định buổi chiều → 13:30-17:30

2. Khi có thời gian cụ thể:
   - Nếu thời gian nằm trong buổi sáng (8:30-12:00) → tính là buổi sáng
   - Nếu thời gian nằm trong buổi chiều (13:30-17:30) → tính là buổi chiều
   - Nếu thời gian nằm ngoài giờ làm việc → báo lỗi và không trả về leave_info

Nếu có ý định nghỉ phép và xác định được thời gian, trả về JSON dạng:
{{
  "intent": "leave_request",
  "api_url": "https://mbi.sapotacorp.vn/api/MissionAPI/SubmitReasonOffWork",
  "leave_info": {{
    "from_date": "<ngày bắt đầu tính từ ngày hiện tại>",
    "to_date": "<ngày kết thúc tính từ ngày hiện tại>",
    "time_off": "<số giờ nghỉ>",
    "reason": "<lý do nghỉ>"
  }}
}}

Nếu có ý định xuất file lương, trả về JSON dạng:
{{
  "intent": "payslip_export",
  "api_url": "https://mbi.sapotacorp.vn/api/UserAPI/OutputExcelPayslip",
  "month": "<năm-tháng>"
}}

Nếu KHÔNG cần gọi API hoặc không xác định được thời gian nghỉ, trả về:
{{
  "intent": "none",
  "api_url": "",
  "leave_info": null
}}

Danh sách intent được hỗ trợ:
- "leave_request": "https://mbi.sapotacorp.vn/api/MissionAPI/SubmitReasonOffWork"
- "leave_history": "https://mbi.sapotacorp.vn/User/NghiPhep/History"
- "leave_balance": "https://mbi.sapotacorp.vn/User/NghiPhep/Balance"
- "payslip_export": "https://mbi.sapotacorp.vn/api/UserAPI/OutputExcelPayslip"

Phân tích các từ khóa:
- Đăng ký nghỉ, xin nghỉ, tạo đơn nghỉ → leave_request
- Xem lịch sử nghỉ, đơn đã gửi → leave_history
- Số ngày nghỉ còn lại → leave_balance
- Xuất file lương, tải file lương → payslip_export

Ví dụ về phân tích và trả về JSON (Sử dụng Ngày hiện tại: {current_date.strftime('%m %d %Y')}):

Người dùng: "nghỉ sáng mai vì bị cảm" → 
{{
  "intent": "leave_request",
  "api_url": "https://mbi.sapotacorp.vn/api/MissionAPI/SubmitReasonOffWork",
  "leave_info": {{
    "from_date": "{next_day.strftime('%m %d %Y')} 08:30",
    "to_date": "{next_day.strftime('%m %d %Y')} 12:00",
    "time_off": "4",
    "reason": "bị cảm"
  }}
}}

Người dùng: "xuất file lương tháng 3" → 
{{
  "intent": "payslip_export",
  "api_url": "https://mbi.sapotacorp.vn/api/UserAPI/OutputExcelPayslip",
  "month": "2024-03"
}}

Câu người dùng: "{user_input}"
Chỉ trả về JSON, không giải thích.
"""
    raw_response = get_response(prompt)
    response = clean_response(raw_response)
    
    try:
        parsed = json.loads(response)
        # Only calculate hours if leave_info exists and dates are present
        if parsed.get("intent") == "leave_request" and parsed.get("leave_info"):
             leave_info = parsed["leave_info"]
             from_date = leave_info.get("from_date")
             to_date = leave_info.get("to_date")
             if from_date and to_date:
                hours = calculate_leave_hours(from_date, to_date)
                leave_info["time_off"] = str(hours)
                parsed["leave_info"] = leave_info # Update parsed with calculated hours
             else:
                 # If dates are missing, set intent to none
                 parsed["intent"] = "none"
                 parsed["api_url"] = ""
                 parsed["leave_info"] = None

        return json.dumps(parsed)
    except Exception as e:
        # If JSON parsing fails or any other error, return intent none
        print(f"Lỗi phân tích JSON hoặc xử lý khác trong detect_api_intent: {e}")
        return json.dumps({ "intent": "none", "api_url": "", "leave_info": None })

def chat_response(user_input):
    prompt = f"Bạn là một trợ lý AI thân thiện. Trả lời người dùng tự nhiên: {user_input}"
    return get_response(prompt)

if __name__ == "__main__":
    print("🤖 Chatbot đã sẵn sàng! (Gõ 'exit' để thoát)")
    while True:
        user_input = input("\n👤 Bạn: ")
        if user_input.lower() == "exit":
            break

        intent_result = detect_api_intent(user_input)

        try:
            parsed = json.loads(intent_result)
            if parsed.get("intent") == "none":
                reply = chat_response(user_input)
                print(f"\n🤖 {reply}")
            else:
                print("\n🤖 Phân tích yêu cầu API:")
                print(json.dumps(parsed, indent=2, ensure_ascii=False))
        except json.JSONDecodeError:
            print("🤖 Không hiểu rõ ý định. Đang trả lời bình thường...")
            reply = chat_response(user_input)
            print(f"\n🤖 {reply}")
