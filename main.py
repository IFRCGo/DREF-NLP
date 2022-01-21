# main.py for DREF_PARSETAG

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import StreamingResponse
from importlib import resources
import io
from enum import Enum

from dref_parsing.parser_utils import *
from dref_tagging.prediction import predict_tags_any_length

app = FastAPI()

# This Enum class allows us to see a dropdown menu with possible choices
class OuputFormat(str, Enum):
    json = "json"
    csv = "csv"


# Once Subdimension is found, this function helps select the corresponding Dimension
def get_Dimension_from_Subdimension(subdim, spec):
    if subdim in list(spec.index):
        return spec.loc[subdim,'Dimension']
    return 'ERROR: No Dimension matches this Subdimension :('



# ------------------------------------------------------
# Main function for Parsing+Tagging
@app.get("/parse_and_tag/{output_format}")
async def parse_and_tag(output_format: OuputFormat, 
    Appeal_code: str = Query(
        'MDRDO013',
        title="Appeal code",
        description="Starts with 'MDR' followed by 5 symbols. <br> Some available codes: DO013, BO014, CL014, AR017, VU008, TJ029, SO009, PH040, RS014, FJ004, CD031, MY005, LA007, CU006, AM006",
        min_length=8,
        max_length=8)):
    """
    App for Parsing PDFs of DREF Final Reports and Tagging Excerpts.   
    <b>Input</b>: Appeal code of the report, MDR*****  
    <b>Output</b>:  
    &nbsp;&nbsp; a list of excerpts extracted from the PDF with its features: 'Learning', 'DREF_Sector',  
    &nbsp;&nbsp; and global features: 'Hazard', 'Country', 'Date', 'Region', 'Appeal code'.  
    &nbsp;&nbsp; The output can be given as a dictionary in json format, or as a csv file for download

    The app uses IFRC GO API to determine the global features (call 'appeal')  
    and to get the URL of the PDF report (call 'appeal_document')

    <b>Possible errors</b>:  
    <ul>
    <li> Appeal code doesn't have a DREF Final Report in IFRC GO appeal database 
    <li> PDF URL for Appeal code was not found using IFRC GO API call appeal_document
    <li> PDF Parsing didn't work
    </ul>
    """

    # Renaming: In the program we call it 'lead', while IFRC calls it 'Appeal_code'
    lead = Appeal_code 
    
    # ---------------------------------------------------------
    # Parsing PDF
    try:
        # excerpts (and other relevant columns)
        all_parsed = parse_PDF_combined(lead)
    except ExceptionNotInAPI:
        raise HTTPException(status_code=404, 
                            detail=f"{lead} doesn't have a DREF Final Report in IFRC GO appeal database")
    except ExceptionNoURLforPDF:
        raise HTTPException(status_code=404, 
                            detail=f"PDF URL for Appeal code {lead} was not found using IFRC GO API call appeal_document")
    except:
        raise HTTPException(status_code=500, detail="PDF Parsing didn't work by some reason")

    df = all_parsed[['Modified Excerpt', 'Learning', 'DREF_Sector', 'lead', 'Hazard', 'Country', 'Date', 'Region']].copy() #,'position', 'DREF_Sector_id']]

    # -----------------------------------------------------------
    # Tagging excerpts and cleaning/renaming

    df.loc[:,'Subdimension'] = df['Modified Excerpt'].apply(lambda x: predict_tags_any_length(x)[0])
    # Split to "row per tag"
    df = df.explode('Subdimension')

    # Define Dimensions from Subdimensions using a dics from csv file
    with resources.path("dref_tagging.config", "DREF_spec.csv") as DREF_spec_file:
        spec = pd.read_csv(DREF_spec_file).set_index('Subdimension')    
    
    df['Dimension'] = df['Subdimension'].apply(lambda x: get_Dimension_from_Subdimension(x, spec))     
    df = df.fillna('Unknown')   

    df = df.rename(columns={'lead':'Appeal code','Modified Excerpt':'Excerpt'})

    # reorder columns
    cols_order = ['Excerpt', 'Learning', 'DREF_Sector', 'Appeal code', 'Hazard', 'Country', 'Date', 'Region', 'Dimension' ,'Subdimension']
    df = df[cols_order]

    # -----------------------------------
    # Return DataFrame as Json or Csv:

    if output_format == 'json':
        return df.to_dict()

    else: 
        # prepare csv output
        stream = io.StringIO()
        # NB: comma as a separator works OK even if there exist commas in some excerpts 
        # since pandas is smart to insert quotes where needed
        df.to_csv(stream, index = False, sep=',')

        response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
        response.headers["Content-Disposition"] = "attachment; filename=export.csv"
        return response    


# *********************************************************************

@app.get("/refresh/")
async def reload_GO_API_data():
    """
    Reload data from GO database.  
    This may be needed since the Parse-and-Tag app downloads data from GO
    the first time it runs and never checks for updates.  
    To refresh data from GO, run this app.
    """    
    try:
        initialize_apdo(refresh=True)
        initialize_aadf(refresh=True)

        # NB: we need to do import again, 
        # otherwise updated apdo, aadf won't be accessible here
        # (even though they got updated in parser_utils)
        from dref_parsing.parser_utils import apdo, aadf
        output = f'GO API Reload: {len(aadf)} items in appeal, {len(apdo)} items in appeal_documents'
        output += ' (only DREF Final Reports are selected)'
    except:
        raise HTTPException(status_code=500, detail="Error while accessing GO API data")
    return output 

    # Command to start API:
    # uvicorn main:app --reload



