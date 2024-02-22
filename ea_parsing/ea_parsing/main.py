from fastapi import FastAPI, Query, HTTPException
from ea_parsing.appeal_document import Appeal

app = FastAPI()

@app.post("/parse/")
async def run_parsing(
    mdr_code: str = Query(
        default='MDRKE043',
        title="MDR code",
        description="Starts with 'MDR' followed by 5 symbols. <br> Some available codes: DO013, BO014, CL014, AR017, VU008, TJ029, SO009, PH040, RS014, FJ004, CD031, MY005, LA007, CU006, AM006",
        min_length=8,
        max_length=8,
        regex="^MDR[A-Z0-9]{5}$"
        )
    ):
    """
    </ul>
    """
    # Get appeal final report
    appeal = Appeal(mdr_code=mdr_code)
    final_report = appeal.final_report
    if final_report is not None:

        # Get lessons learned
        lessons_learned = final_report.lessons_learned

        return lessons_learned