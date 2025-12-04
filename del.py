import requests

BASE_URL = "https://projects.vestaging.in:9093/api/v1"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzY0OTIzNzkyLCJqdGkiOiI5MTQ0ZjMwMTNiN2E0OWIzYmQ1ZDQ4ODIzZWIxMTRhMSIsInVzZXJfaWQiOjM1fQ.ahPrF3fYuYeMP60LyjcjOYpi_d4zCETE8lAVTPiH3Yg"

headers = {
    "Authorization": f"Bearer {TOKEN}"
}

# Example: Get project by slug
project_slug = "sandipghosh-ai-scrum-master"
r = requests.get(
    f"{BASE_URL}/projects/by_slug?slug={project_slug}",
    headers=headers,
    verify=False
)
# print(r.json())
print("\n---\n")
print(r.text[:300])
print("Status:", r.status_code)
print("Headers:", r.headers)
print("Body:", r.text[:500])