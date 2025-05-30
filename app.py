from flask import Flask, render_template, request, jsonify, session, send_file
from gemini_chatbot_intent import detect_api_intent, chat_response, call_real_api, export_payslip
import json
import requests
from datetime import datetime

app = Flask(__name__)
app.secret_key = "your_secret_key"  

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message")
    
    if session.get("waiting_for_leave_details"):
        session.pop("waiting_for_leave_details")
        intent_result = detect_api_intent(user_input)
        try:
            parsed = json.loads(intent_result)
            if parsed.get("intent") == "leave_request" and parsed.get("leave_info"):
                leave_info = parsed.get("leave_info")
                if not leave_info.get("reason"):
                    session["waiting_for_leave_reason"] = True
                    session["pending_leave_info"] = leave_info
                    return jsonify(type="chat", result="📝 Vẫn thiếu lý do nghỉ. Bạn vui lòng cho biết lý do?")

                result = submit_leave_request(
                    userid="1013",
                    username="michael",
                    from_date=leave_info.get("from_date"),
                    to_date=leave_info.get("to_date"),
                    time_off=leave_info.get("time_off"),
                    reason=leave_info.get("reason")
                )
                if result.get("success"):
                    return jsonify(type="chat", result="✅ Đã gửi đơn nghỉ thành công!")
                else:
                    return jsonify(type="chat", result=f"❌ {result.get('message')}")
            else:
                reply = chat_response("Không hiểu rõ thông tin nghỉ phép bạn vừa cung cấp.")
                return jsonify(type="chat", result=reply)
        except json.JSONDecodeError:
            reply = chat_response("Không hiểu rõ thông tin nghỉ phép bạn vừa cung cấp (lỗi phân tích).")
            return jsonify(type="chat", result=reply)

    if session.get("waiting_for_leave_reason"):
        leave_info = session.get("pending_leave_info", {})
        leave_info["reason"] = user_input 
        
        result = submit_leave_request(
            userid="1013",
            username="michael",
            from_date=leave_info.get("from_date"),
            to_date=leave_info.get("to_date"),
            time_off=leave_info.get("time_off"),
            reason=leave_info.get("reason")
        )
        session.pop("waiting_for_leave_reason")
        session.pop("pending_leave_info")
        
        if result.get("success"):
            return jsonify(type="chat", result="✅ Đã gửi đơn nghỉ thành công!")
        else:
            return jsonify(type="chat", result=f"❌ {result.get('message')}")
    
    intent_result = detect_api_intent(user_input)
    try:
        parsed = json.loads(intent_result)
        
        if parsed is None:
             reply = chat_response("Không hiểu rõ yêu cầu của bạn.")
             return jsonify(type="chat", result=reply)
             
        if parsed.get("intent") == "none":
            reply = chat_response(user_input)
            return jsonify(type="chat", result=reply)
        elif parsed.get("intent") == "leave_request":
            leave_info = parsed.get("leave_info", {})
            if not leave_info or leave_info is None:
                 session["waiting_for_leave_details"] = True
                 session["pending_leave_intent"] = "leave_request"
                 return jsonify(type="chat", result="📝 Bạn vui lòng cho biết chi tiết thời gian và lý do nghỉ?")

            if not leave_info.get("reason"):
                session["waiting_for_leave_reason"] = True
                session["pending_leave_info"] = leave_info
                return jsonify(type="chat", result="📝 Bạn vui lòng cho biết lý do nghỉ?")
            
            result = submit_leave_request(
                userid="1013",
                username="michael",
                from_date=leave_info.get("from_date"),
                to_date=leave_info.get("to_date"),
                time_off=leave_info.get("time_off"),
                reason=leave_info.get("reason")
            )
            if result.get("success"):
                return jsonify(type="chat", result="✅ Đã gửi đơn nghỉ thành công!")
            else:
                return jsonify(type="chat", result=f"❌ {result.get('message')}")
        elif parsed.get("intent") == "payslip_export":
            month = parsed.get("month")
            if not month:
                return jsonify(type="chat", result="❌ Không xác định được tháng cần xuất file lương")
            
            result = export_payslip(month)
            
            if result.get("success"):
                if result.get("download_url"):
                    return jsonify({
                        "type": "download_link",
                        "url": result["download_url"],
                        "message": "✅ File lương đã được xuất thành công."
                    })
                elif result.get("message"):
                    return jsonify(type="chat", result=f"✅ {result.get('message')}")
                else:
                    return jsonify(type="chat", result="✅ Yêu cầu xử lý thành công nhưng không rõ kết quả tải file.")
            else:
                return jsonify(type="chat", result=f"❌ {result.get('message')}")
        elif parsed.get("intent") == "point_export":
            result = export_point_report()
            if result.get("success"):
                return jsonify({
                    "type": "download_link",
                    "url": result["download_url"],
                    "message": "✅ Báo cáo điểm đã được xuất thành công."
                })
            else:
                return jsonify(type="chat", result=f"❌ {result.get('message')}")
        else:
            api_result = call_real_api(parsed["api_url"], user_input)
            return jsonify(type="api", result=api_result)
    except json.JSONDecodeError:
        reply = chat_response("Không hiểu rõ phản hồi từ AI.")
        return jsonify(type="chat", result=reply)
    except Exception as e:
        print(f"Lỗi không xác định trong route /chat: {e}")
        return jsonify(type="chat", result=f"❌ Đã xảy ra lỗi không xác định: {str(e)}")

@app.route("/download-payslip", methods=["GET"])
def download_payslip():
    return jsonify({"error": "Tính năng tải file trực tiếp không hỗ trợ do cách API trả về dữ liệu."}), 400

def submit_leave_request(userid, username, from_date, to_date, time_off, reason):
    """
    Gửi yêu cầu nghỉ phép đến API
    """
    try:
        url = f"https://mbi.sapotacorp.vn/api/MissionAPI/SubmitReasonOffWork"
        time_off_int = int(time_off) if time_off else 0
        params = {
            "userid": userid,
            "username": username,
            "fr": from_date,
            "to": to_date,
            "timeOff": time_off_int, 
            "reason": reason
        }
        headers = {
            "Content-Type": "application/json"
        }
        response = requests.get(url, params=params, headers=headers)
        print("API response:", response.status_code, response.text)
        
        if response.status_code == 200:
            return {"success": True, "message": "Gửi yêu cầu nghỉ phép thành công"}
        else:
            return {"success": False, "message": f"Lỗi khi gửi yêu cầu: {response.text}"}
            
    except Exception as e:
        return {"success": False, "message": f"Lỗi: {str(e)}"}

@app.route("/submit-leave", methods=["POST"])
def handle_leave_request():
    try:
        data = request.get_json()
        
        userid = data.get("userid")
        username = data.get("username")
        from_date = data.get("from_date")
        to_date = data.get("to_date")
        time_off = data.get("time_off")
        reason = data.get("reason")
        
        result = submit_leave_request(
            userid=userid,
            username=username,
            from_date=from_date,
            to_date=to_date,
            time_off=time_off,
            reason=reason
        )
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi: {str(e)}"})

def export_point_report():
    """
    Xuất báo cáo điểm từ API
    """
    try:
        url = "https://mbi.sapotacorp.vn/api/UserAPI/OutputExcelReportUser"
        headers = {
            "accept": "application/json, text/plain, */*",
            "authorization": "michael##Hamia*10124##4", 
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "referer": "https://mbi.sapotacorp.vn/"
        }
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            response_text = response.text.strip()
            if response_text:
                print(f"API point report response text: {response_text}")
                if response_text.startswith('"') and response_text.endswith('"'):
                    response_text = response_text[1:-1]

                if response_text.startswith('http://') or response_text.startswith('https://'):
                    download_url = response_text
                else:
                    download_url = f"https://mbi.sapotacorp.vn{response_text}"
                print(f"Constructed point report download URL: {download_url}")
                return {"success": True, "download_url": download_url}
            else:
                return {"success": False, "message": "API xuất báo cáo điểm phản hồi thành công (200 OK) nhưng nội dung trống."}
        else:
            return {"success": False, "message": f"Lỗi từ API xuất báo cáo điểm: {response.status_code} - {response.text}"}

    except Exception as e:
        return {"success": False, "message": f"Lỗi kết nối hoặc xử lý khi gọi API xuất báo cáo điểm: {str(e)}"}

if __name__ == "__main__":
    app.run(debug=True)
