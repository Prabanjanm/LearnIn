from fastapi import APIRouter

router = APIRouter(

    prefix="/notes",

    tags=["Note"]

)


@router.get("/")

def list_items():

    return {

        "message":"Note List"

    }


@router.get("/{item_id}")

def details(item_id:int):

    return {

        "message":"Note Details",

        "id":item_id

    }
