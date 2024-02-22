from fastapi import FastAPI, Query, HTTPException
from ea_parsing.appeal_document import Appeal, AppealDocument

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
    final_report_details = appeal.final_report_details
    if final_report_details is not None:

        # Get lessons learned
        final_report = AppealDocument(
            document_url=final_report_details['document_url']
        )
        lessons_learned = final_report.lessons_learned

        return lessons_learned