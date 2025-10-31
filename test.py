import requests

# temporary download URLs (replace these with your actual current links)
rice_url = "https://www.data.gov.in/backend/dms/v1/ogdp/resource/download/7530429/json/eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJkYXRhLmdvdi5pbiIsImF1ZCI6ImRhdGEuZ292LmluIiwiaWF0IjoxNzYxODk1MDEzLCJleHAiOjE3NjE4OTUzMTMsImRhdGEiOnsibmlkIjo3NTMwNDI5fX0.6y3MXeHyvpzBkcQdmR0wV1UKP3sXk3R_sZR9FiSwQ2g"
jowar_url = "https://www.data.gov.in/backend/dms/v1/ogdp/resource/download/7531049/json/eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJkYXRhLmdvdi5pbiIsImF1ZCI6ImRhdGEuZ292LmluIiwiaWF0IjoxNzYxODk1MTEyLCJleHAiOjE3NjE4OTU0MTIsImRhdGEiOnsibmlkIjo3NTMxMDQ5fX0.TBtKMlL4Qy3cqb5cG1i4rwibMPvTV2bWfxBgop88vDk"

# destination folder
output_dir = "data_json"

# download Rice JSON
r1 = requests.get(rice_url, timeout=60)
if r1.status_code == 200:
    with open(f"{output_dir}/rice.json", "wb") as f:
        f.write(r1.content)
    print("✅ rice.json downloaded successfully")
else:
    print("❌ Rice download failed:", r1.status_code)

# download Jowar JSON
r2 = requests.get(jowar_url, timeout=60)
if r2.status_code == 200:
    with open(f"{output_dir}/jowar.json", "wb") as f:
        f.write(r2.content)
    print("✅ jowar.json downloaded successfully")
else:
    print("❌ Jowar download failed:", r2.status_code)
