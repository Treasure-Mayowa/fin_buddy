import os, re, requests, json
from dotenv import load_dotenv

load_dotenv()

def get_advice(text):

#     url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key="

#     key = os.getenv("GEMINI_API_KEY")

#     headers = {
#         "Content-Type": "application/json"
#     }
#     data = {
#     "contents": [
#             {
#                 "parts": [
#                     {
#                         # "text": "You're a metrics analyzer. Your job is to go through the following JSON metrics and generate a summary detailing any anomalies in the metrics and what to investigate to resolve those anomalies, keep in mind that you're to prioritize energy optimization, cost savings, environmental impact (Carbon emission). Also research the company and tailor the summary to the policies of the organization.\n {}".format(json.dumps(report))
#                         "text": """without exceedeing 4096 characters, Assume you are a Nigerian financial consultant and respond to the following in a concise manner

#                         {}
# """.format(text)
#                     }
#                 ]
#             }
#         ]
#     }

    api_key = os.getenv("OPENROUTER_API_KEY")
    response = requests.post(
      url="https://openrouter.ai/api/v1/chat/completions",
      headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "<YOUR_SITE_URL>", # Optional. Site URL for rankings on openrouter.ai.
        "X-Title": "<YOUR_SITE_NAME>", # Optional. Site title for rankings on openrouter.ai.
      },
      data=json.dumps({
        "model": "google/gemini-2.5-flash-image-preview:free",
        "messages": [
          {
            "role": "user",
            "content": [
              {
                "type": "text",
                "text": """without exceedeing 4096 characters, Assume you are a Nigerian financial consultant whose name is FinBuddy and respond to the following in a concise manner

                        {}
""".format(text)
            }
            #   {
            #     "type": "image_url",
            #     "image_url": {
            #       "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"
            #     }
            #   }
            ]
          }
        ],

      })
    )

    # response = requests.post(url + key, headers=headers, json=data)
    print(response.json())

    # advice:str = (response.json()["candidates"][0]["content"]["parts"][0]["text"])
    advice:str = (response.json()["choices"][0]["message"]["content"])
    advice = re.sub(r'\*\*(.*?)\*\*', r'\1', advice)
    if advice[0] == '"':
        advice = advice[1:-1]
    return(advice)