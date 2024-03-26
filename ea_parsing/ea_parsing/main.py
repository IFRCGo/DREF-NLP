from fastapi import FastAPI, Query
import pandas as pd
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
        regex="^MDR[A-Z0-9]{5,7}$"
        )
):
    """
    </ul>
    """
    # Get appeal final report
    appeal = Appeal(mdr_code=mdr_code)
    final_report = appeal.final_report
    if final_report is not None:

        # Get lessons learned and challenges
        lessons_learned = final_report.lessons_learned
        challenges = final_report.challenges

        # Convert into the same format as DREF_parsing
        results = {
            'Challenges': challenges,
            'Lessons Learnt': lessons_learned
        }
        for section_type, section in results.items():
            results[section_type] = pd.DataFrame(section)\
                .drop(columns=['title'])\
                .explode('items')\
                .rename(columns={'sector_title': 'DREF_Sector', 'items': 'Excerpt'})
            results[section_type]['Learning'] = section_type

        # Combine the dataframes
        results = pd.concat(results.values()).dropna(subset=['Excerpt']).reset_index(drop=True)

        # Add in Appeal information
        results['Appeal code'] = mdr_code
        results['Hazard'] = appeal.dtype['name']
        results['Country'] = appeal.country['name']
        results['Date'] = appeal.start_date[:10]
        results['Region'] = appeal.region['region_name']

        # Order the columns
        results = results[['Excerpt', 'Learning', 'DREF_Sector', 'Appeal code', 'Hazard', 'Country', 'Date', 'Region']]

        return results.to_dict()
