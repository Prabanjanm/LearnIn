from fastapi.responses import JSONResponse


def success(message, data=None):

    return JSONResponse(

        status_code=200,

        content={

            "success": True,

            "message": message,

            "data": data

        }

    )


def error(message, status_code=400):

    return JSONResponse(

        status_code=status_code,

        content={

            "success": False,

            "message": message

        }

    )