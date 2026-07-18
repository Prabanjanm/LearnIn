from fastapi import APIRouter

router = APIRouter(

    prefix="/blogs",

    tags=["Blog"]

)


@router.get("/")

def list_items():

    return {

        "message":"Blog List"

    }


@router.get("/{item_id}")

def details(item_id:int):

    return {

        "message":"Blog Details",

        "id":item_id

    }
