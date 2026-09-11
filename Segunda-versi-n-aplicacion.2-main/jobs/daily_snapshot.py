import os
import sys

import requests


base_url = os.environ["APP_BASE_URL"].rstrip("/")
secret = os.environ["CRON_SECRET"]
response = requests.post(
    base_url + "/api/tareas/captura-diaria",
    headers={"X-Cron-Secret": secret},
    timeout=120,
)
print(response.status_code, response.text)
response.raise_for_status()
sys.exit(0)
