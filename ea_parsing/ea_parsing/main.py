from fastapi import FastAPI, Query, HTTPException
from ea_parsing.utils import extract_text_and_fontsizes, get_ifrc_go_final_report

#from ea_parsing.parser_utils import extract_text_and_fontsizes, get_ifrc_go_final_report
#from ea_parsing.appeal_document import AppealDocument


app = FastAPI()


@app.post("/parse/")
async def run_parsing(
    mdr_code: str = Query(
        default='MDRDO013',
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
    # Get the Emergency Appeal document
    document = get_ifrc_go_final_report(mdr_code=mdr_code)
    lines = extract_text_and_fontsizes(document=document)
    
    return lines