import os, re, requests
from dotenv import load_dotenv

load_dotenv()

def get_advice(text):

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key="

    key = os.getenv("GEMINI_API_KEY")

    headers = {
        "Content-Type": "application/json"
    }
    data = {
    "contents": [
            {
                "parts": [
                    {
                        # "text": "You're a metrics analyzer. Your job is to go through the following JSON metrics and generate a summary detailing any anomalies in the metrics and what to investigate to resolve those anomalies, keep in mind that you're to prioritize energy optimization, cost savings, environmental impact (Carbon emission). Also research the company and tailor the summary to the policies of the organization.\n {}".format(json.dumps(report))
                        "text": """without exceedeing 4096 characters, Assume you are a Nigerian financial consultant and respond to the following in a concise manner

                        {}
""".format(text)
                    }
                ]
            }
        ]
    }

    response = requests.post(url + key, headers=headers, json=data)

    advice:str = (response.json()["candidates"][0]["content"]["parts"][0]["text"])
    advice = re.sub(r'\*\*(.*?)\*\*', r'\1', advice)
    return(advice)