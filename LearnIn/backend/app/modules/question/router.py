from fastapi import APIRouter

router = APIRouter(

    prefix="/questions",

    tags=["Question"]

)


@router.get("/")

def list_items():

    return {

        "message":"Question List"

    }


@router.get("/{item_id}")

def details(item_id:int):

    return {

        "message":"Question Details",

        "id":item_id

    }
