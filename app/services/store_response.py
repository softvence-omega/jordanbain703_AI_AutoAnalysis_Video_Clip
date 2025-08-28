import requests
from app.config import BACKEND_URL


def string_to_array(string):
    return string.split(",") if string else []

def store_response_in_db(id, auth_token, response_data, credit_usage):
    response_route_url = f"{BACKEND_URL}/clip-segments/{id}"
    headers = {
        "Authorization": f"Bearer {auth_token}"
    }

    data = {
        "status": "completed", 
        "clip_number": len(response_data), 
        "creditUsed": round(credit_usage),
        "clips": []
    }

    for clip in response_data:
        relatedTopic = string_to_array(clip["relatedTopic"])
        data["clips"].append({
            "viralScore": clip["viralScore"],
            "relatedTopic": relatedTopic,
            "transcript": clip["transcript"],
            "videoUrl": clip["videoUrl"],
            "clipEditorUrl": clip["clipEditorUrl"],
            "videoMsDuration": clip["videoMsDuration"],
            "videoId": clip["videoId"],
            "title": clip["title"],
            "viralReason": clip["viralReason"],
        })

    print(f"Posting clip-segments to {response_route_url}")
    # print("Payload:", data)

    try:
        response = requests.post(response_route_url, json=data, headers=headers)
        print("Response Status Code:", response.status_code)
        # print("Response Body:", response.text)
        response.raise_for_status()  # JSON এ রূপান্তরের আগে কল করো
        return {"status": "success"}
    except requests.exceptions.RequestException as e:
        print("Error storing clip segments in DB:", e)
        return {"status": "error"}


def store_in_db(request_data, response_data, credit_usage, main_video_duration):
    if request_data.videoType == 1:
        videoSourceInName = "cloudinary"
    elif request_data.videoType == 2:
        videoSourceInName = "youtube"
    elif request_data.videoType == 3:
        videoSourceInName = "google_drive"

    response_route_url = f"{BACKEND_URL}/makeclip/create"
    headers = {
        "Authorization": f"Bearer {request_data.auth_token}"
    }

    data = {
        "videoSourceInNumber": request_data.videoType,
        "videoSourceInName": videoSourceInName,
        "videoUrl": request_data.url,
        "clipCount": request_data.maxClipNumber,
        "perClipDuration": request_data.clipLength,
        "creditUsed": round(credit_usage),
        "duration": main_video_duration,
        "langCode": request_data.langCode,
        "prompt": request_data.prompt,
        "templateId": request_data.templateId,
    }

    print("Creating main clip entry...")
    try:
        response = requests.post(response_route_url, json=data, headers=headers)
        print("Response Status Code:", response.status_code)
        # print("Response Body:", response.text)
        response.raise_for_status()
        resp_json = response.json()
        # print("Storing request in DB:", resp_json)

        # stored Response in db
        id = resp_json['data']['id']
        response = store_response_in_db(id, request_data.auth_token, response_data, credit_usage)
        if response['status'] == 'error':
            print("Failed to store clip segments.")
            return None
        return id

    except requests.exceptions.RequestException as e:
        print("Error storing main clip in DB:", e)
        return None

if __name__ == "__main__":
    requests_data = {
        "auth_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiJjbWV0bWQ1Ym4wMDAwdW14Y3kxazNncnlwIiwiZW1haWwiOiJtZGFybWFueWEuaEBnbWFpbC5jb20iLCJyb2xlIjoiVVNFUiIsImlhdCI6MTc1NjM0OTMyNCwiZXhwIjoxNzU2MzUyOTI0fQ.6G4PtTzCe8Tu6yzeCnm-MQUraQsoKrodJ1gFCLLbQD0",
        "url": "https://drive.google.com/file/d/1qvuBXrmWqwr_uAzIHan6yHQbu5LrNJaj/view?usp=sharing",
        "videoType": 3,
        "langCode": "en",
        "clipLength": 1,
        "maxClipNumber": 2,
        "templateId": "2",
        "prompt": ""
    }

    response_data = [
        {
        "viralScore": "8.2",
        "relatedTopic": "[\"decision,preparedness,knowledge,growth,transformation\"]",
        "transcript": "15 months have passed, and it feels like yesterday that we took the most important decision of our lives. And if you think about it, not much has changed. We continue to make big decisions. But today there is a difference. We are far more prepared, better informed, and we have each built our reserve of knowledge against what's to come.",
        "videoUrl": "https://res.cloudinary.com/dbnf4vmma/video/upload/v1756291694/reels/b8buvgri3nofrna1c954.mp4",
        "clipEditorUrl": "https://vizard.ai/editor?id=127998213&type=clip",
        "videoMsDuration": 25920,
        "videoId": 18730592,
        "title": "Big Decisions, But Now We're Far More Prepared",
        "viralReason": "Highlights a personal growth journey emphasizing how the same big decisions feel different when you're better prepared—a universal yet motivating insight.",
        "duration": 41.495964
        },
        {
        "viralScore": "7.8",
        "relatedTopic": "[\"MBA,dream,turbulent\",\"times,inspiration,growth\"]",
        "transcript": "The MBA has been a dream, a dream for most of us before it even began, a dream that we all lived through during very turbulent times. However, it was a dream that we have all fulfilled. And today we stand here awakened and inspired only to dream bigger.",
        "videoUrl": "https://res.cloudinary.com/dbnf4vmma/video/upload/v1756291719/reels/jaqifccaw4uorencyqci.mp4",
        "clipEditorUrl": "https://vizard.ai/editor?id=127998212&type=clip",
        "videoMsDuration": 20800,
        "videoId": 18730591,
        "title": "We All Had a Dream Amid Turbulent Times – Here's How It Changed Us",
        "viralReason": "Starts with a relatable, emotional reflection on a shared dream endured through tough times, which resonates and inspires viewers to consider their own journeys.",
        "duration": 36.36263
        }
    ]

    id = store_in_db(requests_data, response_data, 15.5, main_video_duration=300)
    print("Stored main clip ID:", id)