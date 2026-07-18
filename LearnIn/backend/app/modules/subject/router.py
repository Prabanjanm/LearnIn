from fastapi import APIRouter

router = APIRouter(

    prefix="/subjects",

    tags=["Subject"]

)


@router.get("/")

def list_items():

    return {

        "message":"Subject List"

    }


@router.get("/{item_id}")

def details(item_id:int):

    return {

        "message":"Subject Details",

        "id":item_id

    }
