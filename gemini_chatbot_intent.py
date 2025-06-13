import google.generativeai as genai
import json
import requests
from datetime import datetime, timedelta
import os
import pandas as pd
from openpyxl import load_workbook

genai.configure(api_key="AIzaSyB8d5o2veAopoa5FlcVxKqm3z8LNkP19Zk")
model = genai.GenerativeModel('models/gemini-2.0-flash')
chat = model.start_chat()

def extract_important_info(html_content):
    return html_content

def call_real_api(api_url):
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
        return response.text.strip() if response.text else ""
    except Exception as e:
        print(f"Lỗi khi gọi Gemini: {str(e)}")
        return "Error: Unable to get response from AI."

def clean_response(response):
    if not response:
        return ""
    response = response.strip()
    if response.startswith('```') and response.endswith('```'):
        response = response[3:-3]
    if response.lower().startswith('json'):
        response = response[4:]
    return response.strip()

def export_payslip(month):
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
            response_text = response.text.strip()
            if response_text:
                if response_text.startswith('"') and response_text.endswith('"'):
                    response_text = response_text[1:-1]

                download_url = f"https://mbi.sapotacorp.vn{response_text}"
                print(f"Constructed download URL: {download_url}")
                return {"success": True, "download_url": download_url}
            else:
                return {"success": False, "message": "API phản hồi thành công (200 OK) nhưng nội dung trống."}
        else:
            return {"success": False, "message": f"Lỗi từ API xuất file: {response.status_code} - {response.text}"}

    except Exception as e:
        return {"success": False, "message": f"Lỗi kết nối hoặc xử lý khi gọi API xuất file: {str(e)}"}

def get_working_hours(date):
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

def validate_leave_dates(from_date, to_date):
    try:
        start = datetime.strptime(from_date, "%m %d %Y %H:%M")
        end = datetime.strptime(to_date, "%m %d %Y %H:%M")
        current = datetime.now()

        # Kiểm tra ngày nghỉ không được trong quá khứ
        if start < current:
            return False, "❌ Không thể đăng ký nghỉ trong quá khứ"

        # Kiểm tra thời gian nghỉ không được quá 30 ngày
        if (end - start).days > 30:
            return False, "❌ Thời gian nghỉ không được vượt quá 30 ngày"

        # Kiểm tra ngày nghỉ phải là ngày làm việc
        current_date = start
        while current_date.date() <= end.date():
            if current_date.weekday() >= 5:  # Thứ 7 (5) và Chủ nhật (6)
                return False, "❌ Không thể đăng ký nghỉ vào cuối tuần"
            current_date += timedelta(days=1)

        return True, None
    except Exception as e:
        return False, f"❌ Lỗi khi kiểm tra ngày nghỉ: {str(e)}"

def calculate_leave_hours(from_date, to_date):
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

                # Xử lý buổi sáng
                if current.date() == start.date():
                    morning_start = max(morning_start, start)
                if current.date() == end.date():
                    morning_end = min(morning_end, end)

                if morning_start < morning_end:
                    morning_hours = (morning_end - morning_start).total_seconds() / 3600
                    total_hours += morning_hours

                # Xử lý buổi chiều
                if current.date() == start.date():
                    afternoon_start = max(afternoon_start, start)
                if current.date() == end.date():
                    afternoon_end = min(afternoon_end, end)

                if afternoon_start < afternoon_end:
                    afternoon_hours = (afternoon_end - afternoon_start).total_seconds() / 3600
                    total_hours += afternoon_hours

            current += timedelta(days=1)

        return int(round(total_hours))
    except Exception as e:
        print(f"Error calculating leave hours: {str(e)}")
        return 0

def detect_api_intent(user_input):
    current_date = datetime.now()
    next_day = current_date + timedelta(days=1)
    days_until_monday = (0 - current_date.weekday() + 7) % 7
    next_monday = current_date + timedelta(days=days_until_monday)
    if next_monday.date() == current_date.date():
        next_monday += timedelta(days=7)

    days_until_friday = (4 - current_date.weekday() + 7) % 7
    next_friday = current_date + timedelta(days=days_until_friday)
    if next_friday.date() == current_date.date():
        next_friday += timedelta(days=7)

    prompt = f"""
Bạn là trợ lý AI. Phân tích yêu cầu của người dùng và xác định intent phù hợp.

Thông tin thời gian làm việc:
- Làm việc từ thứ 2 đến thứ 6
- Buổi sáng: 8:30 - 12:00
- Buổi chiều: 13:30 - 17:30
- Không làm việc thứ 7 và chủ nhật
- Không thể đăng ký nghỉ trong quá khứ
- Thời gian nghỉ tối đa là 30 ngày

Lưu ý quan trọng về xử lý ngày tháng và giờ:
- Ngày hiện tại là: {current_date.strftime('%m %d %Y %H:%M')}
- Định dạng ngày giờ trả về phải là: "MM DD YYYY HH:mm" (ví dụ: "06 04 2025 08:30")
- LUÔN LUÔN sử dụng ngày hiện tại làm mốc thời gian
- Nếu ngày nghỉ trong quá khứ hoặc vượt quá 30 ngày, trả về intent "none"

Cách xử lý thời gian:
1. Khi chỉ có ngày (ví dụ: "mai", "thứ 2"):
   - Nếu không chỉ định buổi → mặc định là cả ngày (8:30-17:30)
   - Nếu chỉ định buổi sáng → 8:30-12:00
   - Nếu chỉ định buổi chiều → 13:30-17:30

2. Khi có thời gian cụ thể:
   - Nếu thời gian nằm trong buổi sáng (8:30-12:00) → tính là buổi sáng
   - Nếu thời gian nằm trong buổi chiều (13:30-17:30) → tính là buổi chiều
   - Nếu thời gian nằm ngoài giờ làm việc → báo lỗi và không trả về leave_info

3. Xử lý các từ khóa thời gian:
   - "mai" = ngày tiếp theo
   - "hôm nay" = ngày hiện tại
   - "thứ X" = ngày thứ X trong tuần hiện tại (nếu đã qua thì tính tuần sau)
   - "tuần này" = tuần hiện tại
   - "tuần sau" = tuần tiếp theo
   - "tháng này" = tháng hiện tại
   - "tháng sau" = tháng tiếp theo
   - "đầu tuần" = thứ 2
   - "cuối tuần" = thứ 6
   - "tuần tới" = tuần sau
   - "tuần trước" = tuần trước

4. Xử lý giờ:
   - "sáng" = 8:30-12:00
   - "chiều" = 13:30-17:30
   - "cả ngày" = 8:30-17:30
   - "nửa ngày" = 4 giờ (mặc định là buổi sáng)
   - "nửa buổi" = 4 giờ (mặc định là buổi sáng)
   - "1 giờ", "2 giờ", "3 giờ", "4 giờ" = số giờ tương ứng
   - Giờ cụ thể (ví dụ: "9h", "9:00") → giữ nguyên giờ đó

5. Xử lý nhiều ngày liên tiếp:
   - Khi có nhiều ngày (ví dụ: "thứ 2, 3") → tính từ ngày đầu đến ngày cuối
   - Khi có dấu phẩy hoặc "và" giữa các ngày → tính là nhiều ngày liên tiếp
   - Khi có từ "đến" hoặc "tới" → tính từ ngày đầu đến ngày cuối
   - Khi có từ "từ" → tính từ ngày đó đến ngày hiện tại
   - Khi có từ "trong" → tính trong khoảng thời gian đó

6. Xử lý các trường hợp đặc biệt:
   - "nghỉ ngay" = nghỉ ngay lập tức
   - "nghỉ gấp" = nghỉ ngay lập tức
   - "nghỉ khẩn cấp" = nghỉ ngay lập tức
   - "nghỉ có kế hoạch" = nghỉ theo lịch đã định
   - "nghỉ dài ngày" = nghỉ nhiều ngày liên tiếp
   - "nghỉ ngắn ngày" = nghỉ 1-2 ngày

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

Nếu có ý định xuất file point, trả về JSON dạng:
{{
  "intent": "point_export",
  "api_url": "https://mbi.sapotacorp.vn/api/UserAPI/OutputExcelReportUser"
}}

Nếu KHÔNG cần gọi API hoặc không xác định được thời gian nghỉ, trả về:
{{
  "intent": "none",
  "api_url": "",
  "leave_info": null
}}

Danh sách intent được hỗ trợ:
- "leave_request": "https://mbi.sapotacorp.vn/api/MissionAPI/SubmitReasonOffWork"
- "payslip_export": "https://mbi.sapotacorp.vn/api/UserAPI/OutputExcelPayslip"
- "point_export": "https://mbi.sapotacorp.vn/api/UserAPI/OutputExcelReportUser"

Phân tích các từ khóa:
- Đăng ký nghỉ, xin nghỉ, tạo đơn nghỉ, off → leave_request
- Xuất file lương, tải file lương → payslip_export
- Xuất file point, tải báo cáo user, xuất báo cáo user → point_export

Ví dụ về phân tích và trả về JSON (Sử dụng Ngày hiện tại: {current_date.strftime('%m %d %Y')}):

Người dùng: "nghỉ sáng mai vì làm remote" →
{{
  "intent": "leave_request",
  "api_url": "https://mbi.sapotacorp.vn/api/MissionAPI/SubmitReasonOffWork",
  "leave_info": {{
    "from_date": "{next_day.strftime('%m %d %Y')} 08:30",
    "to_date": "{next_day.strftime('%m %d %Y')} 12:00",
    "time_off": "4",
    "reason": "làm remote"
  }}
}}

Người dùng: "xin nghỉ thứ 5 tuần này vì bận việc gia đình" (Giả sử Ngày hiện tại là Thứ 2 {current_date.strftime('%m %d %Y')}) →
{{
  "intent": "leave_request",
  "api_url": "https://mbi.sapotacorp.vn/api/MissionAPI/SubmitReasonOffWork",
  "leave_info": {{
    "from_date": "{next_friday.strftime('%m %d %Y')} 08:30",
    "to_date": "{next_friday.strftime('%m %d %Y')} 17:30",
    "time_off": "8",
    "reason": "bận việc gia đình"
  }}
}}

Người dùng: "thứ 2, 3 tuần sau tôi làm remote" →
{{
  "intent": "leave_request",
  "api_url": "https://mbi.sapotacorp.vn/api/MissionAPI/SubmitReasonOffWork",
  "leave_info": {{
    "from_date": "{next_monday.strftime('%m %d %Y')} 08:30",
    "to_date": "{(next_monday + timedelta(days=1)).strftime('%m %d %Y')} 17:30",
    "time_off": "16",
    "reason": "làm remote"
  }}
}}

Người dùng: "nghỉ gấp 2 giờ vì bị ốm" →
{{
  "intent": "leave_request",
  "api_url": "https://mbi.sapotacorp.vn/api/MissionAPI/SubmitReasonOffWork",
  "leave_info": {{
    "from_date": "{current_date.strftime('%m %d %Y %H:%M')}",
    "to_date": "{(current_date + timedelta(hours=2)).strftime('%m %d %Y %H:%M')}",
    "time_off": "2",
    "reason": "bị ốm"
  }}
}}

Người dùng: "xuất file lương tháng này" (Giả sử Ngày hiện tại là {current_date.strftime('%m %d %Y')}) →
{{
  "intent": "payslip_export",
  "api_url": "https://mbi.sapotacorp.vn/api/UserAPI/OutputExcelPayslip",
  "month": "{current_date.strftime('%Y-%m')}"
}}

Người dùng: "xuất file lương tháng 3" →
{{
  "intent": "payslip_export",
  "api_url": "https://mbi.sapotacorp.vn/api/UserAPI/OutputExcelPayslip",
  "month": "2024-03"
}}

Người dùng: "xuất file point" →
{{
  "intent": "point_export",
  "api_url": "https://mbi.sapotacorp.vn/api/UserAPI/OutputExcelReportUser"
}}

Câu người dùng: "{user_input}"
Chỉ trả về JSON, không giải thích.
"""
    raw_response = get_response(prompt)
    response = clean_response(raw_response)

    try:
        parsed = json.loads(response)
        if parsed.get("intent") == "leave_request" and parsed.get("leave_info"):
             leave_info = parsed["leave_info"]
             from_date = leave_info.get("from_date")
             to_date = leave_info.get("to_date")
             if from_date and to_date:
                # Kiểm tra tính hợp lệ của ngày nghỉ
                is_valid, error_message = validate_leave_dates(from_date, to_date)
                if not is_valid:
                    return json.dumps({ 
                        "intent": "error", 
                        "message": error_message,
                        "api_url": "", 
                        "leave_info": None 
                    })

                # Tính số giờ nghỉ
                hours = calculate_leave_hours(from_date, to_date)
                if hours == 0:
                    return json.dumps({ 
                        "intent": "error", 
                        "message": "❌ Không thể tính số giờ nghỉ",
                        "api_url": "", 
                        "leave_info": None 
                    })

                leave_info["time_off"] = str(hours)
                parsed["leave_info"] = leave_info
             else:
                 parsed["intent"] = "error"
                 parsed["message"] = "❌ Không xác định được thời gian nghỉ"
                 parsed["api_url"] = ""
                 parsed["leave_info"] = None

        return json.dumps(parsed)
    except Exception as e:
        return json.dumps({ 
            "intent": "error", 
            "message": f"❌ Lỗi xử lý yêu cầu: {str(e)}",
            "api_url": "", 
            "leave_info": None 
        })

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