from fastapi import APIRouter

router = APIRouter(

    prefix="/mock_tests",

    tags=["MockTest"]

)


@router.get("/")

def list_items():

    return {

        "message":"MockTest List"

    }


@router.get("/{item_id}")

def details(item_id:int):

    return {

        "message":"MockTest Details",

        "id":item_id

    }
