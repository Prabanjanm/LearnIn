from pydantic import BaseModel


class DownloadBase(BaseModel):
    pass


class DownloadCreate(DownloadBase):
    pass


class DownloadUpdate(DownloadBase):
    pass


class DownloadResponse(DownloadBase):

    id: int

    class Config:
        from_attributes = True
