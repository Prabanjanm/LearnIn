from fastapi import APIRouter

router = APIRouter(

    prefix="/downloads",

    tags=["Download"]

)


@router.get("/")

def list_items():

    return {

        "message":"Download List"

    }


@router.get("/{item_id}")

def details(item_id:int):

    return {

        "message":"Download Details",

        "id":item_id

    }
