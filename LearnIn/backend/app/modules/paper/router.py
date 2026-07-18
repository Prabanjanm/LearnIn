from fastapi import APIRouter

router = APIRouter(

    prefix="/papers",

    tags=["Paper"]

)


@router.get("/")

def list_items():

    return {

        "message":"Paper List"

    }


@router.get("/{item_id}")

def details(item_id:int):

    return {

        "message":"Paper Details",

        "id":item_id

    }
