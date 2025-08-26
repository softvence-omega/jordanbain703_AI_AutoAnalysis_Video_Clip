import requests
from app.config import VIZARD_API_KEY
import json 

async def run_clip_generation(project_id):
    url = f"https://elb-api.vizard.ai/hvizard-server-front/open-api/v1/project/query/{project_id}"
    headers = {
        "Content-Type": "application/json",
        "VIZARDAI_API_KEY": VIZARD_API_KEY
    }
    response = requests.get(url, headers=headers)

    return json.loads(response.text)



async def main():
    res = await run_clip_generation('23176124')
    print("response------------", res['videos'])
import asyncio
if __name__=='__main__':
    asyncio.run(main())