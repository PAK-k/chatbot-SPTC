import google.generativeai as genai

# Thay bằng API key của bạn
genai.configure(api_key="AIzaSyB8d5o2veAopoa5FlcVxKqm3z8LNkP19Zk")

models = genai.list_models()

for model in models:
    print(f"- {model.name}")
