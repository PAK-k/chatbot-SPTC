import google.generativeai as genai
import json
import requests
from datetime import datetime, timedelta
import pandas as pd
import os
import pandas as pd

genai.configure(api_key="AIzaSyB8d5o2veAopoa5FlcVxKqm3z8LNkP19Zk")
model = genai.GenerativeModel('models/gemini-2.0-flash')
chat = model.start_chat()

def extract_important_info(url, html_content, city=None):
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
    elif "nghiphep/balance" in url.lower():
        return {
            "type": "link",
            "url": url,
            "title": "🗓️ Xem số ngày nghỉ còn lại",
            "message":
                """📅 Thông tin số ngày nghỉ:
- Tổng số ngày nghỉ phép năm
- Số ngày đã sử dụng
- Số ngày còn lại
- Thống kê theo loại nghỉ phép
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

def find_header_row(file_path, required_columns, max_rows_to_check=20):
    """
    Tìm dòng header (index bắt đầu từ 0) chứa đầy đủ các cột bắt buộc
    """
    engine = 'openpyxl' if file_path.lower().endswith('.xlsx') else 'xlrd'
    try:
        preview_df = pd.read_excel(file_path, engine=engine, header=None, nrows=max_rows_to_check)
    except Exception as e:
        raise ValueError(f"Không thể đọc file Excel để dò dòng tiêu đề: {e}")
    
    for i in range(len(preview_df)):
        row_values = preview_df.iloc[i].astype(str).str.strip().str.upper().tolist()
        if all(any(req_col in val for val in row_values) for req_col in required_columns):
            return i
    return None

def read_excel_tasks(file_path):
    """
    Đọc danh sách task từ file Excel
    """
    try:
        # Đọc file Excel để tìm dòng tiêu đề
        print("Bắt đầu đọc file Excel...")
        
        # Đọc 20 dòng đầu tiên để tìm dòng tiêu đề
        df_header = pd.read_excel(file_path, nrows=20)
        
        # Tìm dòng tiêu đề
        header_row = find_header_row(file_path, ['MÃ DỰ ÁN', 'MÃ DEV'])
        if not header_row:
            return {
                "success": False,
                "message": "Không tìm thấy dòng tiêu đề trong file Excel"
            }
            
        print(f"Đã tìm thấy dòng tiêu đề ở dòng số {header_row + 1} (index: {header_row})")
        
        # Đọc lại file với dòng tiêu đề đã tìm được
        df_header = pd.read_excel(file_path, header=header_row)
        
        # In ra các cột đọc được để debug
        print("Các cột đọc được từ file Excel (gốc -> chuẩn hóa):", {col: col.upper() for col in df_header.columns})
        
        # Chuẩn hóa tên cột
        original_columns = {col: col.upper() for col in df_header.columns}
        
        # Ánh xạ tên cột chuẩn hóa với tên tiếng Anh và chỉ mục
        standardized_mapping_and_index = {
            'MÃ DỰ ÁN': {'english_name': 'project_id', 'index': None},
            'MÃ DEV': {'english_name': 'dev_id', 'index': None}
        }
        
        found_columns = {}
        found_column_indices = {}
        missing_required_original_columns = []
        
        # Tìm từng cột cần thiết
        for standard_col in ['MÃ DỰ ÁN', 'MÃ DEV']:
            for original_col_name, standardized_name in original_columns.items():
                if standardized_name == standard_col:
                    found_columns[standardized_mapping_and_index[standard_col]['english_name']] = original_col_name
                    col_index = df_header.columns.get_loc(original_col_name)
                    found_column_indices[standardized_mapping_and_index[standard_col]['english_name']] = col_index
                    standardized_mapping_and_index[standard_col]['index'] = col_index
                    break
            else:
                missing_required_original_columns.append(standard_col)
                
        if missing_required_original_columns:
            return {
                "success": False,
                "message": f"File Excel thiếu các cột bắt buộc: {', '.join(missing_required_original_columns)}"
            }
            
        print(f"Đã tìm thấy chỉ mục các cột cần thiết: {found_column_indices}")
        
        # Đọc dữ liệu chính từ file, bỏ qua 6 hàng đầu (trước dữ liệu) và chỉ đọc các cột cần thiết bằng chỉ mục
        print("Bỏ qua 6 hàng đầu tiên (skiprows=6) và đọc dữ liệu từ các chỉ mục cột đã xác định.")
        
        cols_by_index = sorted(found_column_indices.values())
        print(f"Chỉ mục cột sẽ sử dụng để đọc dữ liệu: {cols_by_index}")
        
        if file_path.lower().endswith('.xlsx'):
            # Khi dùng skiprows và usecols bằng index, pandas đọc data từ hàng skiprows + 1
            df = pd.read_excel(file_path, engine='openpyxl', skiprows=6, usecols=cols_by_index, header=None, dtype={0: str, 1: str})
        else:
            df = pd.read_excel(file_path, engine='xlrd', skiprows=6, usecols=cols_by_index, header=None, dtype={0: str, 1: str})
            
        print("Raw DataFrame after skiprows and usecols:")
        print(df)
        
        # Đổi tên cột để dễ xử lý
        df.columns = ['project_id', 'dev_id']
        
        # Lọc bỏ các dòng có giá trị NaN
        df = df.dropna()
        
        # Thêm số thứ tự cho mỗi task
        df['index'] = range(1, len(df) + 1)
        
        # Chuyển đổi dữ liệu thành list các dict
        tasks = df.to_dict('records')
        
        print("DataFrame sau khi đọc dữ liệu, lọc theo chỉ mục và đổi tên cột:")
        print(df)
        
        return {
            "success": True,
            "tasks": tasks
        }
        
    except Exception as e:
        print(f"Lỗi khi đọc file Excel: {str(e)}")
        return {
            "success": False,
            "message": f"Lỗi khi đọc file Excel: {str(e)}"
        }

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

Lưu ý quan trọng về xử lý ngày tháng và giờ:
- Ngày hiện tại là: {current_date.strftime('%m %d %Y %H:%M')}
- Định dạng ngày giờ trả về phải là: "MM DD YYYY HH:mm" (ví dụ: "06 04 2025 08:30")
- LUÔN LUÔN sử dụng ngày hiện tại làm mốc thời gian

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

4. Xử lý giờ:
   - "sáng" = 8:30-12:00
   - "chiều" = 13:30-17:30
   - "cả ngày" = 8:30-17:30
   - Giờ cụ thể (ví dụ: "9h", "9:00") → giữ nguyên giờ đó

5. Xử lý nhiều ngày liên tiếp:
   - Khi có nhiều ngày (ví dụ: "thứ 2, 3") → tính từ ngày đầu đến ngày cuối
   - Khi có dấu phẩy hoặc "và" giữa các ngày → tính là nhiều ngày liên tiếp
   - Khi có từ "đến" hoặc "tới" → tính từ ngày đầu đến ngày cuối

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

Lưu ý quan trọng về xử lý tháng xuất lương:
1. Khi người dùng yêu cầu xuất lương tháng hiện tại:
   - Nếu đang trong tháng hiện tại (ví dụ: ngày 15/3) → trả về tháng hiện tại (2024-03)
   - Nếu đang trong tháng mới (ví dụ: ngày 1/4) → trả về tháng trước (2024-03)
2. Khi người dùng chỉ định tháng cụ thể:
   - Nếu chỉ có tháng (ví dụ: "tháng 3") → tự động thêm năm hiện tại (2024-03)
   - Nếu có cả năm (ví dụ: "tháng 3/2024") → sử dụng đúng năm đó (2024-03)
3. Khi người dùng dùng từ khóa "tháng này":
   - Nếu đang trong tháng hiện tại → trả về tháng hiện tại
   - Nếu đang trong tháng mới → trả về tháng trước

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
- "leave_history": "https://mbi.sapotacorp.vn/User/NghiPhep/History"
- "payslip_export": "https://mbi.sapotacorp.vn/api/UserAPI/OutputExcelPayslip"
- "point_export": "https://mbi.sapotacorp.vn/api/UserAPI/OutputExcelReportUser"
- "create_task": "https://mbi.sapotacorp.vn/api/TaskAPI/CreateTask"
- "create_tasks_from_excel": "https://mbi.sapotacorp.vn/api/TaskAPI/CreateTask"

Phân tích các từ khóa:
- Đăng ký nghỉ, xin nghỉ, tạo đơn nghỉ, off → leave_request
- Xem lịch sử nghỉ, đơn đã gửi → leave_history
- Xuất file lương, tải file lương → payslip_export
- Xuất file point, tải báo cáo user, xuất báo cáo user → point_export
- Tạo task, thêm task, tạo công việc → create_task
- Tạo task từ Excel, import task từ Excel, tạo nhiều task từ file → create_tasks_from_excel

Nếu có ý định tạo task, trả về JSON dạng:
{{
  "intent": "create_task",
  "api_url": "https://mbi.sapotacorp.vn/api/TaskAPI/CreateTask",
  "task_info": {{
    "project_id": "<id dự án>",
    "dev_id": "<id developer>"
  }}
}}

Nếu có ý định tạo task từ file Excel, trả về JSON dạng:
{{
  "intent": "create_tasks_from_excel",
  "api_url": "https://mbi.sapotacorp.vn/api/TaskAPI/CreateTask",
  "excel_info": {{
    "file_path": "<đường dẫn file Excel>"
  }}
}}

Ví dụ về phân tích và trả về JSON (Sử dụng Ngày hiện tại: {current_date.strftime('%m %d %Y')}):

Người dùng: "nghỉ sáng mai vì làm remote" →
{{
  "intent": "leave_request",
  "api_url": "https://mbi.sapotacorp.vn/api/MissionAPI/SubmitReasonOffWork",
  "leave_info": {{
    "from_date": "{next_day.strftime('%m %d %Y')} 08:30",
    "to_date": "{next_day.strftime('%m %d %Y')} 12:00",
    "time_off": "4",
    "reason": "làm remote"}}
}}

Người dùng: "xin nghỉ thứ 5 tuần này vì bận việc gia đình" (Giả sử Ngày hiện tại là Thứ 2 {current_date.strftime('%m %d %Y')}) →
{{
  "intent": "leave_request",
  "api_url": "https://mbi.sapotacorp.vn/api/MissionAPI/SubmitReasonOffWork",
  "leave_info": {{
    "from_date": "{next_friday.strftime('%m %d %Y')} 08:30",
    "to_date": "{next_friday.strftime('%m %d %Y')} 17:30",
    "time_off": "8",
    "reason": "bận việc gia đình"}}
}}

Người dùng: "thứ 2, 3 tuần sau tôi làm remote" →
{{
  "intent": "leave_request",
  "api_url": "https://mbi.sapotacorp.vn/api/MissionAPI/SubmitReasonOffWork",
  "leave_info": {{
    "from_date": "{next_monday.strftime('%m %d %Y')} 08:30",
    "to_date": "{(next_monday + timedelta(days=1)).strftime('%m %d %Y')} 17:30",
    "time_off": "16",
    "reason": "làm remote"}}
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

Người dùng: "tạo task để làm remote" →
{{
  "intent": "create_task",
  "api_url": "https://mbi.sapotacorp.vn/api/TaskAPI/CreateTask",
  "task_info": {{
    "project_id": "<id dự án>",
    "dev_id": "<id developer>"
  }}
}}

Người dùng: "tạo task từ Excel" →
{{
  "intent": "create_tasks_from_excel",
  "api_url": "https://mbi.sapotacorp.vn/api/TaskAPI/CreateTask",
  "excel_info": {{
    "file_path": "<đường dẫn file Excel>"
  }}
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
                hours = calculate_leave_hours(from_date, to_date)
                leave_info["time_off"] = str(hours)
                parsed["leave_info"] = leave_info
             else:
                 parsed["intent"] = "none"
                 parsed["api_url"] = ""
                 parsed["leave_info"] = None

        return json.dumps(parsed)
    except Exception as e:
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
