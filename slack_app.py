from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from flask import Flask
from gemini_chatbot_intent import detect_api_intent, chat_response, call_real_api, export_payslip, read_excel_tasks
from app import submit_leave_request, export_point_report, create_task
import json
import os
from dotenv import load_dotenv
import requests
import tempfile
from slack_sdk import WebClient

load_dotenv()

slack_app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

user_sessions = {}

def download_slack_file(file_id, file_path):
    """Tải file từ Slack về máy local"""
    try:
        print(f"Bắt đầu tải file với ID: {file_id}")
        
        client = WebClient(token=os.environ.get('SLACK_BOT_TOKEN'))
        
        try:
            response = client.files_info(file=file_id)
            if not response["ok"]:
                error = response.get('error')
                if error == 'missing_scope':
                    print("Bot thiếu quyền files:read. Vui lòng thêm quyền này vào bot và cài đặt lại app.")
                    return False
                print(f"Lỗi khi lấy thông tin file: {error}")
                return False
                
            file_info = response["file"]
            print(f"File info: {file_info}")
            
            file_url = file_info.get("url_private")
            if not file_url:
                print("Không tìm thấy URL tải file")
                return False
                
            headers = {
                "Authorization": f"Bearer {os.environ.get('SLACK_BOT_TOKEN')}"
            }
            response = requests.get(file_url, headers=headers)
            
            if response.status_code != 200:
                print(f"Lỗi khi tải file: {response.status_code} - {response.text}")
                return False
                
            with open(file_path, 'wb') as f:
                f.write(response.content)
                
            print(f"Đã ghi file thành công vào: {file_path}")
            
        except Exception as e:
            print(f"Lỗi khi tải file content: {str(e)}")
            return False
        
        if not os.path.exists(file_path):
            print("File không tồn tại sau khi tải")
            return False
            
        file_size = os.path.getsize(file_path)
        print(f"File size sau khi tải: {file_size} bytes")
        
        if file_size == 0:
            print("File trống sau khi tải")
            return False
            
        try:
            import zipfile
            with zipfile.ZipFile(file_path) as z:
                return True
        except zipfile.BadZipFile:
            print("File không phải là file Excel hợp lệ")
            return False
            
    except Exception as e:
        print(f"Lỗi khi tải file từ Slack: {str(e)}")
        return False

def process_message(text, user_id):
    """Xử lý tin nhắn và trả về phản hồi phù hợp"""
    if user_sessions.get(user_id, {}).get("waiting_for_leave_details"):
        user_sessions[user_id].pop("waiting_for_leave_details")
        intent_result = detect_api_intent(text)
        try:
            parsed = json.loads(intent_result)
            if parsed.get("intent") == "leave_request" and parsed.get("leave_info"):
                leave_info = parsed.get("leave_info")
                if not leave_info.get("reason"):
                    user_sessions[user_id]["waiting_for_leave_reason"] = True
                    user_sessions[user_id]["pending_leave_info"] = leave_info
                    return "📝 Vẫn thiếu lý do nghỉ. Bạn vui lòng cho biết lý do?"

                result = submit_leave_request(
                    userid="1013",
                    username="michael",
                    from_date=leave_info.get("from_date"),
                    to_date=leave_info.get("to_date"),
                    time_off=leave_info.get("time_off"),
                    reason=leave_info.get("reason")
                )
                if result.get("success"):
                    return "✅ Đã gửi đơn nghỉ thành công!"
                else:
                    return f"❌ {result.get('message')}"
            else:
                return chat_response("Không hiểu rõ thông tin nghỉ phép bạn vừa cung cấp.")
        except json.JSONDecodeError:
            return chat_response("Không hiểu rõ thông tin nghỉ phép bạn vừa cung cấp (lỗi phân tích).")

    if user_sessions.get(user_id, {}).get("waiting_for_leave_reason"):
        leave_info = user_sessions[user_id].get("pending_leave_info", {})
        leave_info["reason"] = text
        
        result = submit_leave_request(
            userid="1013",
            username="michael",
            from_date=leave_info.get("from_date"),
            to_date=leave_info.get("to_date"),
            time_off=leave_info.get("time_off"),
            reason=leave_info.get("reason")
        )
        user_sessions[user_id].pop("waiting_for_leave_reason")
        user_sessions[user_id].pop("pending_leave_info")
        
        if result.get("success"):
            return "✅ Đã gửi đơn nghỉ thành công!"
        else:
            return f"❌ {result.get('message')}"

    if user_sessions.get(user_id, {}).get("waiting_for_task_project"):
        user_sessions[user_id].pop("waiting_for_task_project")
        task_info = user_sessions[user_id].get("pending_task_info", {})
        task_info["project_id"] = text
        user_sessions[user_id]["pending_task_info"] = task_info
        user_sessions[user_id]["waiting_for_task_dev"] = True
        return "📝 Vui lòng nhập ID của developer:"

    if user_sessions.get(user_id, {}).get("waiting_for_task_dev"):
        user_sessions[user_id].pop("waiting_for_task_dev")
        task_info = user_sessions[user_id].get("pending_task_info", {})
        task_info["dev_id"] = text
        user_sessions[user_id]["pending_task_info"] = task_info
        
        result = create_task(
            project_id=task_info.get("project_id"),
            dev_id=task_info.get("dev_id")
        )
        user_sessions[user_id].pop("pending_task_info")
        
        if result.get("success"):
            return "✅ Đã tạo task thành công!"
        else:
            return f"❌ {result.get('message')}"

    if user_sessions.get(user_id, {}).get("waiting_for_excel_file"):
        user_sessions[user_id].pop("waiting_for_excel_file")
        
        if not text:
            return "❌ Vui lòng đính kèm file Excel"
        
        print(f"Bắt đầu xử lý file Excel với ID: {text}")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as temp_file:
            temp_path = temp_file.name
        
        print(f"Tạo file tạm tại: {temp_path}")
        
        if not download_slack_file(text, temp_path):
            return "❌ Không thể tải file Excel từ Slack. Bot cần quyền files:read để tải file. Vui lòng liên hệ admin để cấp quyền."
        
        print(f"File đã được tải về thành công: {temp_path}")
        
        if not os.path.exists(temp_path):
            return "❌ File Excel không tồn tại sau khi tải. Vui lòng thử lại."
            
        file_size = os.path.getsize(temp_path)
        print(f"Kích thước file: {file_size} bytes")
        
        if file_size == 0:
            return "❌ File Excel trống. Vui lòng thử lại."
        
        try:
            print("Bắt đầu đọc file Excel...")
            result = read_excel_tasks(temp_path)
            print(f"Kết quả đọc file: {result}")
            
            try:
                os.remove(temp_path)
                print(f"Đã xóa file tạm: {temp_path}")
            except Exception as e:
                print(f"Lỗi khi xóa file tạm: {str(e)}")
            
            if not result.get("success"):
                return f"❌ {result.get('message')}"
            
            tasks = result.get("tasks", [])
            success_count = 0
            error_count = 0
            error_messages = []
            
            for task in tasks:
                task_result = create_task(
                    project_id=task.get("project_id"),
                    dev_id=task.get("dev_id")
                )
                if task_result.get("success"):
                    success_count += 1
                else:
                    error_count += 1
                    error_messages.append(f"Task '{task.get('task_name')}': {task_result.get('message')}")
            
            response = f"✅ Đã tạo thành công {success_count} task"
            if error_count > 0:
                response += f"\n❌ Không thể tạo {error_count} task:\n" + "\n".join(error_messages)
            return response
            
        except Exception as e:
            print(f"Lỗi khi xử lý file Excel: {str(e)}")
            try:
                os.remove(temp_path)
                print(f"Đã xóa file tạm sau lỗi: {temp_path}")
            except Exception as del_error:
                print(f"Lỗi khi xóa file tạm sau lỗi: {str(del_error)}")
            return f"❌ Lỗi khi xử lý file Excel: {str(e)}"

    try:
        intent_result = detect_api_intent(text)
        parsed = json.loads(intent_result)
        
        if parsed is None or parsed.get("intent") == "none":
            return chat_response(text)
             
        if parsed.get("intent") == "create_tasks_from_excel":
            user_sessions[user_id] = user_sessions.get(user_id, {})
            user_sessions[user_id]["waiting_for_excel_file"] = True
            return "📝 Vui lòng đính kèm file Excel chứa danh sách task cần tạo."
            
        elif parsed.get("intent") == "create_task":
            task_info = parsed.get("task_info", {})
            if not task_info or task_info is None:
                return "❌ Không xác định được thông tin task"
            
            if not task_info.get("project_id"):
                user_sessions[user_id] = user_sessions.get(user_id, {})
                user_sessions[user_id]["waiting_for_task_project"] = True
                user_sessions[user_id]["pending_task_info"] = task_info
                return "📝 Vui lòng nhập ID của dự án:"
            
            if not task_info.get("dev_id"):
                user_sessions[user_id] = user_sessions.get(user_id, {})
                user_sessions[user_id]["waiting_for_task_dev"] = True
                user_sessions[user_id]["pending_task_info"] = task_info
                return "📝 Vui lòng nhập ID của developer:"
            
            result = create_task(
                project_id=task_info.get("project_id"),
                dev_id=task_info.get("dev_id")
            )
            
            if result.get("success"):
                return "✅ Đã tạo task thành công!"
            else:
                return f"❌ {result.get('message')}"
            
        elif parsed.get("intent") == "leave_request":
            leave_info = parsed.get("leave_info", {})
            if not leave_info or leave_info is None:
                user_sessions[user_id] = user_sessions.get(user_id, {})
                user_sessions[user_id]["waiting_for_leave_details"] = True
                user_sessions[user_id]["pending_leave_intent"] = "leave_request"
                return "📝 Bạn vui lòng cho biết chi tiết thời gian và lý do nghỉ?"

            if not leave_info.get("reason"):
                user_sessions[user_id] = user_sessions.get(user_id, {})
                user_sessions[user_id]["waiting_for_leave_reason"] = True
                user_sessions[user_id]["pending_leave_info"] = leave_info
                return "📝 Bạn vui lòng cho biết lý do nghỉ?"
            
            result = submit_leave_request(
                userid="1013",
                username="michael",
                from_date=leave_info.get("from_date"),
                to_date=leave_info.get("to_date"),
                time_off=leave_info.get("time_off"),
                reason=leave_info.get("reason")
            )
            if result.get("success"):
                return "✅ Đã gửi đơn nghỉ thành công!"
            else:
                return f"❌ {result.get('message')}"
            
        elif parsed.get("intent") == "payslip_export":
            month = parsed.get("month")
            if not month:
                return "❌ Không xác định được tháng cần xuất file lương"
            
            result = export_payslip(month)
            if result.get("success"):
                if result.get("download_url"):
                    return f"✅ File lương đã được xuất thành công. Link tải: {result.get('download_url')}"
                elif result.get("message"):
                    return f"✅ {result.get('message')}"
                else:
                    return "✅ Yêu cầu xử lý thành công nhưng không rõ kết quả tải file."
            else:
                return f"❌ {result.get('message')}"
            
        elif parsed.get("intent") == "point_export":
            result = export_point_report()
            if result.get("success"):
                return f"✅ Báo cáo điểm đã được xuất thành công. Link tải: {result.get('download_url')}"
            else:
                return f"❌ {result.get('message')}"
            
        else:
            api_result = call_real_api(parsed["api_url"], text)
            return api_result
            
    except json.JSONDecodeError:
        return chat_response("Không hiểu rõ phản hồi từ AI.")
    except Exception as e:
        return chat_response(f"Đã xảy ra lỗi không xác định: {str(e)}")

def create_task(project_id, dev_id):
    try:
        project_id = int(str(project_id).strip())
        dev_id = int(str(dev_id).strip())
        
        url = "https://mbi.sapotacorp.vn/api/TaskAPI/CreateTask"
        headers = {
            "accept": "application/json, text/plain, */*",
            "authorization": "michael##Hamia*10124##4",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "referer": "https://mbi.sapotacorp.vn/Task/CreateTask",
            "Content-Type": "application/json"
        }
        
        params = {
            "projectID": project_id,
            "iddev": dev_id
        }
        
        response = requests.get(url, params=params, headers=headers)
        print(f"API response: {response.status_code} {response.text}")
        
        if response.status_code == 200:
            return {"success": True, "message": "Tạo task thành công"}
        else:
            error_message = "Lỗi không xác định"
            try:
                error_data = response.json()
                if "Message" in error_data:
                    error_message = error_data["Message"]
                elif "message" in error_data:
                    error_message = error_data["message"]
            except:
                pass
            return {"success": False, "message": f"Lỗi khi tạo task: {error_message}"}
            
    except ValueError as e:
        return {"success": False, "message": f"Giá trị không hợp lệ: {str(e)}"}
    except Exception as e:
        return {"success": False, "message": f"Lỗi khi tạo task: {str(e)}"}

def create_tasks_from_excel(file_path):
    try:
        result = read_excel_tasks(file_path)
        if not result["success"]:
            return result
            
        tasks = result["tasks"]
        if not tasks:
            return {"success": False, "message": "Không tìm thấy task nào trong file Excel"}
            
        success_count = 0
        error_messages = []
        
        for task in tasks:
            if not task["project_id"] or not task["dev_id"]:
                error_messages.append(f"Task {task['index']}: Bỏ qua do thiếu thông tin project_id hoặc dev_id")
                continue
                
            result = create_task(task["project_id"], task["dev_id"])
            if result["success"]:
                success_count += 1
            else:
                error_messages.append(f"Task {task['index']}: {result['message']}")
                
        if success_count > 0:
            message = f"✅ Đã tạo thành công {success_count} task"
            if error_messages:
                message += f"\n❌ {len(error_messages)} task thất bại:\n" + "\n".join(error_messages)
        else:
            message = "❌ Không thể tạo task nào:\n" + "\n".join(error_messages)
            
        return {"success": success_count > 0, "message": message}
        
    except Exception as e:
        return {"success": False, "message": f"Lỗi khi xử lý file Excel: {str(e)}"}

@slack_app.event("message")
def handle_message_events(body, say):
    """Xử lý sự kiện tin nhắn từ Slack"""
    if "bot_id" in body["event"]:
        return
        
    text = body["event"]["text"]
    user_id = body["event"]["user"]
    
    print(f"Nhận tin nhắn từ user {user_id}: {text}")
    
    if "files" in body["event"]:
        print(f"Phát hiện file đính kèm: {body['event']['files']}")
        for file in body["event"]["files"]:
            if file.get("filetype") in ["xlsx", "xls"]:
                print(f"Tìm thấy file Excel: {file}")
                text = file.get("id", "")
                print(f"File ID: {text}")
    
    response = process_message(text, user_id)
    say(text=response)

def start_slack_app():
    """Khởi động Slack app trong chế độ Socket Mode"""
    handler = SocketModeHandler(slack_app, os.environ.get("SLACK_APP_TOKEN"))
    handler.start()

if __name__ == "__main__":
    start_slack_app() 