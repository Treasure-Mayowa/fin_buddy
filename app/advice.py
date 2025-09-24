import os, re, requests, json
from dotenv import load_dotenv

load_dotenv()

def get_advice(text) -> str:
  api_key = os.getenv("OPENROUTER_API_KEY")
  response = requests.post(
    url="https://openrouter.ai/api/v1/chat/completions",
    headers={
      "Authorization": f"Bearer {api_key}",
      "Content-Type": "application/json",
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

  advice:str = (response.json()["choices"][0]["message"]["content"])
  
  advice = re.sub(r'\*\*(.*?)\*\*', r'\1', advice)
  if advice[0] == '"':
      advice = advice[1:-1]
  return(advice)