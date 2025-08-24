from pydantic import BaseModel
from typing import Optional

class paramRequest(BaseModel):
    url: str 
    langCode: str 
    clipLength: int 
    maxClipNumber: int
    templateId: Optional[str] = None  # ✅ Optional


# {"success":true,
#  "message":"Template fetched",
#  "data":{"id":2,
#          "userId":"cmep7jqny0000umf8r98irr0q",
#          "templateName":"My First Template",
#          "platform":"YouTube",
#          "aspectRatio":"16:9",
#          "caption":"AI-generated video",
#          "overlayLogo":"https://res.cloudinary.com/dbt83nrhl/image/upload/v1756022880/templates/logo/k77gwpd7eko1suj8p9we.jpg",
#          "introVideo":"https://res.cloudinary.com/dbt83nrhl/video/upload/v1756022877/templates/intro/hwnaylxzxib1veelqrfv.mp4",
#          "outroVideo":"https://res.cloudinary.com/dbt83nrhl/video/upload/v1756022879/templates/outro/vorfvsdkxesn85devy6u.mp4",
#          "colorTheme":"dark",
#          "isActive":true,
#          "isDeleted":false,
#          "isDefault":false,
#          "createdAt":"2025-08-24T08:07:59.708Z",
#          "updatedAt":"2025-08-24T08:07:59.708Z"}}(.venv) 