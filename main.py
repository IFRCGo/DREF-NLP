# main.py for DREF_PARSETAG

from fastapi import FastAPI, Query, HTTPException
from importlib import resources

from dref_parsing.parser_utils import *
from dref_tagging.prediction import predict_tags_any_length


app = FastAPI()


@app.get("/parse_and_tag/")
async def parse_and_tag(
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
    &nbsp;&nbsp; a dictionary of excerpts extracted from the PDF with its features: 'Learning', 'DREF_Sector',  
    &nbsp;&nbsp; and global features: 'Hazard', 'Country', 'Date', 'Region', 'Appeal code'

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

    df2 = all_parsed[['Modified Excerpt', 'Learning', 'DREF_Sector', 'lead', 'Hazard', 'Country', 'Date', 'Region']].copy() #,'position', 'DREF_Sector_id']]

    # Do tagging
    df2.loc[:,'Subdimension'] = df2['Modified Excerpt'].apply(lambda x: predict_tags_any_length(x)[0])
    # Split to "row per tag"
    df2 = df2.explode('Subdimension')

    # Define Dimensions from Subdimensions using a dics from csv file
    with resources.path("dref_tagging.config", "DREF_spec.csv") as DREF_spec_file:
        spec = pd.read_csv(DREF_spec_file).set_index('Subdimension')    
    
    df2['Dimension'] = df2['Subdimension'].apply(lambda x: spec.loc[x,'Dimension'] if x==x else np.nan)     
    df2 = df2.fillna('Unknown')   

    df2 = df2.rename(columns={'lead':'Appeal code','Modified Excerpt':'Excerpt'})
    return df2.to_dict()

    # For CSV output a different conversion is needed 
    return df2.to_csv(sep='|').split('\n')




@app.get("/refresh/")
async def reload_GO_API_data():
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



