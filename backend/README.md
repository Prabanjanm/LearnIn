py -m venv .venv

.venv\Scripts\activate

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

Tester@123 

http://127.0.0.1:8000