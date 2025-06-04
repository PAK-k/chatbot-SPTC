from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from flask import Flask
from gemini_chatbot_intent import detect_api_intent, chat_response, call_real_api, export_payslip
from app import submit_leave_request, export_point_report
import json
import os
from dotenv import load_dotenv

load_dotenv()

slack_app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

user_sessions = {}

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

    intent_result = detect_api_intent(text)
    try:
        parsed = json.loads(intent_result)
        
        if parsed is None:
            return chat_response("Không hiểu rõ yêu cầu của bạn.")
             
        if parsed.get("intent") == "none":
            return chat_response(text)
            
        if parsed.get("intent") == "leave_request":
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
        return f"❌ Đã xảy ra lỗi không xác định: {str(e)}"

@slack_app.event("message")
def handle_message_events(body, say):
    """Xử lý sự kiện tin nhắn từ Slack"""
    if "bot_id" in body["event"]:
        return
        
    text = body["event"]["text"]
    user_id = body["event"]["user"]
    
    response = process_message(text, user_id)
    say(text=response)

def start_slack_app():
    """Khởi động Slack app trong chế độ Socket Mode"""
    handler = SocketModeHandler(slack_app, os.environ.get("SLACK_APP_TOKEN"))
    handler.start()

if __name__ == "__main__":
    start_slack_app() 