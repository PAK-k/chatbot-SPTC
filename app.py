from flask import Flask, render_template, request, jsonify, session
from gemini_chatbot_intent import detect_api_intent, chat_response, call_real_api
import json
import requests

app = Flask(__name__)
app.secret_key = "your_secret_key"  

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message")
    
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
        if parsed.get("intent") == "none":
            reply = chat_response(user_input)
            return jsonify(type="chat", result=reply)
        elif parsed.get("intent") == "leave_request":
            leave_info = parsed.get("leave_info", {})
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
        else:
            api_result = call_real_api(parsed["api_url"], user_input)
            return jsonify(type="api", result=api_result)
    except json.JSONDecodeError:
        reply = chat_response(user_input)
        return jsonify(type="chat", result=reply)

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

if __name__ == "__main__":
    app.run(debug=True)
