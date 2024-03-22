import pandas as pd
import numpy as np
import sys
import io
import glob
import requests
from ast import literal_eval

import datetime
import dateutil.parser 
from munch import Munch

import tika.parser
import pdfminer.high_level
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTImage, LTFigure, LTTextBox, LTTextBoxHorizontal

pbflag = '!!!Page_Break!!!'
all_bullets = ['•','●','▪','-']

all_pdf_folders = ['../data/PDF-2020',
                   '../data/PDF-API',
                   '../data/PDF-new-template',
                   '../data/PDF-download-2021',
                   '../data/PDF-download-2020']
                   
aadf = pd.DataFrame()
apdo = pd.DataFrame()


class ExceptionNotInAPI(Exception):
    "Lead is not among available API codes (with 'appeal' call)"

class ExceptionNoURLforPDF(Exception):
    "URL for PDF file is not available (with API appeal_document call)"

# ****************************************************************************************
# STRING OPERATIONS
# ****************************************************************************************

# Is char a digit 0-9?
def is_digit(c):
    return c >= '0' and c<='9'

# If char is neither lower or upper case, it is not a letter
def is_char_a_letter(c):
    return c.islower() or c.isupper()

# removes all given symbols from a string
def remove_symbols(s, symbols=[' ']):
    return ''.join([c for c in s if not c in symbols])

# get the bottom line, i.e. text after the last linebreak
def get_bottom_line(s, drop_spaces=False, drop_empty=True):
    if drop_spaces:
        s = remove_symbols(s, symbols=[' '])
    lines = s.split('\n')
    if drop_empty:
        lines = [line for line in lines if line.strip(' ')!='']
    return lines[-1]

# True if there exist at least 2 letters after each other, otherwise it's not a text
def exist_two_letters_in_a_row(ch):
    if len(ch)<2:
        return False
    is_previous_letter = is_char_a_letter(ch[0])
    for c in ch[1:]:
        is_current_letter = is_char_a_letter(c)
        if is_previous_letter and is_current_letter:
            return True
        is_previous_letter = is_current_letter
    return False

# Removes all text after the LAST occurence of pattern, including the pattern
def rstrip_from(s, pattern):
    return s[:s.rfind(pattern)]

# Strip string from special symbols and sequences (from beginning & end)
def strip_all(s, left=True, right=True, symbols=[' ','\n']+all_bullets, 
              start_sequences = ['.','1.','2.','3.','4.','5.','6.','7.','8.','9.']):
    for i in range(20):
        for symb in symbols:
            if left:  s = s.lstrip(symb)
            if right: s = s.rstrip(symb)
            
        for seq in start_sequences:
            if s.startswith(seq):
                s = s[len(seq):]                
    return s        

# Strip string from spaces and linebreaks
def strip_all_empty(s, left=True, right=True):
    return strip_all(s, left=left, right=right, symbols=[' ','\n'], start_sequences = [])       

# Return bullet char if the string starts with a bullet.
# Otherwise - returns an empty string
def starts_with_bullet(s0, bullets=all_bullets):
    s = strip_all_empty(s0, right=False)
    if len(s)==0:
        return ''
    if s[0] in bullets:
        return s[0]
    else:
        return ''

# -------------------------------------------
def drop_spaces_between_linebreaks(txt):
    out = txt
    for i in range(5):
        out = out.replace('\n \n','\n\n')
        out = out.replace('\n  \n','\n\n')
        out = out.replace('\n   \n','\n\n')
        out = out.replace('\n    \n','\n\n')
        out = out.replace('\n     \n','\n\n')
    return out    


# ****************************************************************************************
# Finding Text
# ****************************************************************************************

# Alternative findall can be done using:
# https://docs.python.org/3/library/re.html
# http://www.learningaboutelectronics.com/Articles/How-to-search-for-a-case-insensitive-string-in-text-Python.php

# import re
# re.finditer(pattern, s, flags=re.IGNORECASE)
#>>> text = "He was carefully disguised but captured quickly by police."
#>>> for m in re.finditer(r"\w+ly", text):
#...     print('%02d-%02d: %s' % (m.start(), m.end(), m.group(0)))
#07-16: carefully
#40-47: quickly

# ****************************************************
# Simple case-sensitive version, not used anymore
def findall0(pattern, s, region=True, n=30, nback=-1, pattern2=''):
    if nback<0: nback=n
    ii = []
    i = s.find(pattern)
    while i != -1:
        if region:
            t = s[i-nback : i+n]
            if pattern2!='' and t.count(pattern2)>0:
                t = t.split(pattern2)[0]
            ii.append((i,t))
        else:
            ii.append(i)
        i = s.find(pattern, i+1)
    return ii

# ****************************************************
# Finds all positions of the pattern p in the string s,
# if region=True also outputs the next n chars (and previous nback chars) 
# The text output is cut at pattern2
def findall(pattern, s, region=True, n=30, nback=-1, pattern2='', ignoreCase=True):

    if nback<0: nback=n
    ii = []
    if ignoreCase:
        i = s.lower().find(pattern.lower())
    else:
        i = s.find(pattern)
    while i != -1:
        if region:
            t = s[max(0,i-nback) : i+n]   
            
            # Stop string at pattern2
            
            if pattern2 != '':
                if ignoreCase: index2 = t.lower().find(pattern2.lower())
                else:          index2 = t.find(pattern2)
                if index2 != -1:
                    t = t[:index2]

            ii.append((i,t))
        else:
            ii.append(i)
        i = s.find(pattern, i+1)
    return ii    

# **************************************************************************************
# Wrapper: allows calling findall with a list of patterns 
# (by replacement, i.e. the string fragments can be modified)
def findall_patterns(patterns, s0, region=True, n=30, nback=-1, pattern2='', ignoreCase=True):
    if type(patterns) != list:
        # prepare for usual call 
        pattern = patterns
        s = s0
    else:
        # Replace in s all other patterns with the 0th pattern and then call
        pattern = patterns[0]
        s = s0
        for p in patterns[1:]:
            s = s.replace(p,pattern)
    return findall(pattern=pattern, s=s, region=region, n=n, nback=nback, pattern2=pattern2, ignoreCase=ignoreCase)    


# ****************************************************************************************
# GLOBAL / API
# ****************************************************************************************

# Download PDF and optionally save to file
def download_pdf(url, filename=''):
    pdf_data = requests.get(url).content
    if filename != '':
        with open(filename, 'wb') as handler:
            handler.write(pdf_data)
    return pdf_data

# Possible names for DREF Final Operation Reports.
# Unfortunately the names may vary
DREF_Final_Report_names = [
'DREF Operation Final Report',
'DREF Final Report',
'DREF Operation Final Report 1']
# Filter only relevant DREF reports. Ignore case. 
def filter_DREF_Final_Reports(df, names=DREF_Final_Report_names):
    names_lower = [name.lower() for name in names]
    return df[df.name.apply(lambda x: x.lower() in names_lower)].copy().reset_index(drop=True)
# TODO: Should we include more names here?
# E.g. there are around 500 PDF documents with title "Final Report".
# Are they DREF Final reports where the word 'DREF' was forgotten, or
# a different type of reports? NextBridge cannot possibly know.
# The latest example of such a report is MDRBD024, in Nov-2021
# https://adore.ifrc.org/Download.aspx?FileId=469368
# Other possible name variations include:
# Preliminary DREF Operation Final Report, Final Report 1, DREF Operation Final etc


# get all API results as a df
def download_api_results(call='appeal'):
    href = "https://goadmin.ifrc.org/api/v2/"+call+"/?format=json&limit=300000"
    aa = requests.get(href).json()    
    aadf = pd.DataFrame(aa['results'])
    return aadf

# If global variable aadf is empty, we download it from GO API.
# Always download if refresh=True
def initialize_aadf(refresh = False):

    # Old version:
    # if (not 'aadf' in locals()) and (not 'aadf' in globals()): 
    #     return download_api_results()

    global aadf
    length_ini = len(aadf)
    if refresh or (len(aadf) == 0): 
        aadf = download_api_results(call='appeal')

    # For Debugging:
    if False:
        if refresh:
            aadf.start_date = aadf.start_date.apply(lambda x: 'r'+x)
        else:
            if length_ini == 0:
                aadf.start_date = aadf.start_date.apply(lambda x: 'L0'+x)
            else:
                aadf.start_date = aadf.start_date.apply(lambda x: 'L1'+x)
    return 

# If global variable apdo is empty, we download it from GO API & preprocess
# Always download if refresh=True
def initialize_apdo(refresh = False):
    global apdo
    if refresh or (len(apdo) == 0): 
        apdo = download_api_results(call='appeal_document')
        apdo = filter_DREF_Final_Reports(apdo)
        apdo.appeal = apdo.appeal.astype(str)
    return 


# For a given lead get all global features using an API call
def get_global_features(lead):

    if lead == 'Unknown':
        hazard = country = region = start_date = 'Unknown'
    else:
        initialize_aadf()
        if not lead in aadf.code.unique():
            print('print ERROR: '+lead+' is not among API codes')
            raise ExceptionNotInAPI(f'Error: {lead} is not among API codes')
        
        row = aadf[aadf.code==lead]
        if len(row)!=1:
            print(f'WARNING: {lead} is present in API codes {len(row)} times (must be 1)')
            row = row[0:1]
        
        hazard = get_hazard_from_names(row.name.values[0], row.dtype.values[0]['name'])
        country = row.country.values[0]['name']
        region = row.region.values[0]['region_name']
        start_date = row.start_date.values[0][:10]
    
    output = Munch(lead=lead, Hazard=hazard, Country=country, Region=region, Date=start_date)
    return output

# URL for PDF file, can be used by tika.parser instead of PDF filename
def get_pdf_url(lead):
    initialize_aadf()
    initialize_apdo()
    apdo['appeal'] = apdo['appeal'].apply(lambda x: literal_eval(x) if isinstance(x, str) else x)
    merged = aadf.merge(apdo, left_on=aadf['id'].astype(int), right_on=apdo.appeal.str['id'])
    
    # Lets return all merged df if we dont specify a lead
    if lead=='':
        return merged

    url_list = merged[merged.code==lead].document_url
    if len(url_list)==0:
        print(f'ERROR: No URL for PDF with lead = {lead}')
        raise ExceptionNoURLforPDF(f"no URL for PDF with lead = {lead}")
        
    url = url_list.values[0]
    return url

# IO object for PDF data, can be used by tika & pdfminer instead of PDF filename
def get_pdf_io_object(lead):
    url = get_pdf_url(lead)
    pdf_data = download_pdf(url) # bytes with PDF content
    pdf_io = io.BytesIO(pdf_data)
    return pdf_io

# Complete PDF parsing
def parse_PDF_combined(lead, PDFextras=Munch(), pdf_file = None):
    gf_parsed = get_global_features(lead)
    PDFextras = get_PDFextras([lead], PDFextras, source='api', renew=False, pdf_file = pdf_file)
    exs_parsed, _ = get_CHLLs(lead=lead, PDFextras=PDFextras, source='api', pdf_file = pdf_file)
    all_parsed = exs_parsed.merge(pd.DataFrame([gf_parsed]), on='lead')
    return all_parsed

# ****************************************************************************************
# HAZARDS
# ****************************************************************************************

all_hazards = ['Flood',
 'Drought',
 'Earthquake',
 'Population Movement',
 'Epidemic',
 'Cyclone',
 'Volcanic Eruption',
 'Civil Unrest',
 'Fire',
 'Food Insecurity',
 'Tornado',
 'Transport Accident',
 'Cold Wave',
 'Storm Surge',
 'Heat Wave',
 'Pluvial/Flash Flood']

# Title usually consists of country, separator, and hazard description
def split_report_title(title):
    seps = [' - ','-',': ',':',' ']
    for sep in seps:
        #if sep==seps[4]: print(title)
        try:
            if title.count(sep)>0:
                splitted = title.split(sep,1)
                return [t.strip(' ') for t in splitted]
        except:
            print('ERROR ', title)
    return title, '' 

# split a string into list of words
def get_words_from_string(s):
    ww = s.lower().split(' ')
    ww = [w.strip('-').strip(' ') for w in ww]
    ww = [w for w in ww if w!='']
    return ww

# Finds common words in 2 strings
def get_common_words(s1,s2):
    w1 = get_words_from_string(s1)
    w2 = get_words_from_string(s2)
    common = set(w1).intersection(set(w2))
    return common

# Get Hazard by 'decoding' two strings obtained by API call
def get_hazard_from_names(name, dtype_name):
    if dtype_name in all_hazards:
        return dtype_name
    hazard_from_title = split_report_title(str(name))[1]
    hazard_from_title = hazard_from_title.replace('Floods','Flood').replace('Storms','Storm')
    
    if hazard_from_title in all_hazards:
        return hazard_from_title
    if hazard_from_title in ['Flash Flood','Pluvial']: 
        return 'Pluvial/Flash Flood'  
    if hazard_from_title.lower().count('hailstorm')>0: return 'Cold Wave' # or 'Storm Surge'
    if hazard_from_title.lower().count('strong wind')>0: return 'Storm Surge'
    if hazard_from_title.lower().count('attack')>0: return 'Civil Unrest'
    if hazard_from_title.lower().count('outbreak')>0: return 'Epidemic'
    
    hazards_with_commons = [h for h in all_hazards if len(get_common_words(h,hazard_from_title))>0]
    
    if len(hazards_with_commons)>0:
        return hazards_with_commons[0]

    return 'Other' #'Unknown'
        
# ****************************************************************************************
# SECTORS
# ****************************************************************************************

# Get df with Sector long names and short names (id)
# The long names include true names and nicknames
def get_sectors_df():

    # Dict: Full sector name -> short name (sector ID)
    ids =  {'Health':'Health',
            'Education':'Education',
            'Shelter and Settlements':'Shelter', 
            'Disaster Risk Reduction and Climate Action':'Disaster', 
            'Water Sanitation and Hygiene':'WASH',
            'Livelihoods and Basic Needs':'Live',
            'Strategies for implementation':'Strategies',
            'Protection, Gender and Inclusion':'PGI',
            'Migration and Displacement':'Migration'}
    n_true_names = len(ids) # these are true sector names

    # Add names of 'Strategy' sections too, to link them to 'Strategy' Sector
    for sec in strategy_sections:
        ids[sec] = 'Strategies'

    sectors = pd.DataFrame(ids.items(), columns=['name','id'])
    # Only the first rows are true sector names
    sectors['true name'] = sectors.index < n_true_names
    return sectors

# In case we need a list of all sector names
def all_sector_names():
    sectors = get_sectors_df()
    return sectors[sectors['true name']].name.values

# Get short sector name from a long name
def shorten_sector(sector_name):
    if sector_name.lower().count('livelihoods')>0: return 'Live'
    if sector_name.lower().count('water')>0: return 'WASH'
    if sector_name.lower().count('shelter')>0: return 'Shelter'
    if sector_name.lower().count('inclusion')>0: return 'PGI'
    if sector_name.lower().count('protection')>0: return 'PGI'
    if sector_name.lower().count('disaster')>0: return 'Disaster'
    if sector_name.lower().count('health')>0: return 'Health'

    sectors = get_sectors_df()
    if sector_name.strip() in sectors.id.values:
        return sector_name
    if sector_name.strip() in sectors.name.values:
        return sectors.set_index('name').loc[sector_name.strip(),'id']
    
    return 'Unknown'

def full_sector_name(sector_name):
    sectors = get_sectors_df()
    sectors = sectors[sectors['true name']]
    if sector_name.strip() in sectors.id.values:
        return sectors.set_index('id').loc[sector_name.strip(),'name']
    return 'Unknown'

# ***************************************************
# Find sections and auxiliary functions - for SECTORS
# ***************************************************

# Usually section starts by stating number of people reached
section_markers =  ['\nPeople reached',
                    '\nPeople targeted',
                    '\nPopulation reached',
                    '\nPopulation targeted',
                    '\nTotal number of people reached']

# Later sections that correspond to 'Strategy' Sector
# may have a lot of different names:
strategy_sections =['National Society Strengthening',
                    'National Society Capacity',
                    'Strengthen National Society',
                    'Strategies for Implementation',
                    'International Disaster Response',
                    'Influence others as leading strategic']                    


# True if there is no text (except possibly spaces) when searching for LB backwards
def are_there_only_spaces_before_LB(s):
    before_LB = s.split('\n')[-1]
    return before_LB.strip(' ') == ''

# ---------------------------------------------------------------
# Get a list of section names based on 'classic' section markers
def find_sections_classic(txt):

    # Find text that precedes classic section_markers
    prs = findall_patterns(section_markers, txt, region=True, n=0, nback=100)

    # Several markers can come close to each other, 
    # e.g. 'People reached' & 'People targeted'
    # Then we should keep only the first one:
    pp = [pr[0] for pr in prs] # only positions
    too_close_indices = [i for i in range(1, len(pp)) if pp[i] < pp[i-1] + 100]
    prs = [pr for i,pr in enumerate(prs) if not i in too_close_indices]

    # Take only the bottom line of the text (search for LB backward)
    # assuming that the last line before the marker is section name
    prs = [(pr[0], get_bottom_line(pr[1])) for pr in prs]
    return prs

# ---------------------------------------------------------------
# Get a list of 'Strategic" sections
def find_sections_strategy(txt):

    # Later sections that all correspond to 'Strategy' Sector
    prs = findall_patterns(strategy_sections, txt, region=True, n=0, nback=100)

    # Section Title is always preceeded by linebreak & possibly spaces after it.
    # If not, these are not sections (just plain text), exclude them
    prs = [pr for pr in prs if are_there_only_spaces_before_LB(pr[1])]

    # Name them 'Strategies'
    prs = [(pr[0], 'Strategies') for pr in prs]
    return prs

# --------------------------------------------------------------
# Sections for the new template
def find_sections_new(txt):
    # find what precedes pattern
    patterns = ["reached"]
    prs = findall_patterns(patterns, txt, region=True, n=0, nback=100)

    # keep only if the previous line (or previous word) is 'Persons'
    prs = [pr for pr in prs if get_bottom_line(pr[1], drop_spaces=True)=='Persons']

    prs_processed = []
    for pr in prs:
        # Process string:
        s = pr[1]

        # drop all text starting from 'Persons' 
        s = rstrip_from(s,'Persons')

        s = strip_all_empty(s, left=False)
        s = drop_spaces_between_linebreaks(s)

        # keep what's after multiple linebreaks
        s = s[s.rfind("\n\n\n"):]
        # remove linebreaks
        s = remove_symbols(s, symbols=['\n']).strip(' ')

        # Save string back to tuple:
        prs_processed.append( (pr[0], s) )

    return prs_processed

# ---------------------------------------------------------------
# Get a list of all Section names from PDF text
def find_sections(txt):

    # "Classic" sections, by markers:
    prs1 = find_sections_classic(txt)

    # "Strategy" sections, by names:
    prs2 = find_sections_strategy(txt)

    # New-template sections, by markers:
    prs3 = find_sections_new(txt)

    # Return all combined
    return prs1 + prs2 + prs3

# ---------------------------------------------------------------
# Find section to which a given position in the text belongs 
# (to determine Sector)
def section_from_position(secs, position):
    distances = [(position-sec[0],sec[1]) for sec in secs if position>sec[0]]
    if distances==[]:
        # position is BEFORE all sections
        return 'before'
    # index of the nearest section-start
    isec = np.argmin([dist[0] for dist in distances])
    return secs[isec][1]

# ---------------------------------------------------------------
# Compare True and Parsed sectors and output statistics of how they match
def assess_match_sector(pp):
    df1 = pp.exs_true
    df2 = pp.echs_parsed
    # Sometimes dots are missing at the end:
    df1['Modified Excerpt'] = df1['Modified Excerpt'].apply(lambda x: x.strip('.'))
    df2['Modified Excerpt'] = df2['Modified Excerpt'].apply(lambda x: x.strip('.'))
    # This g helps avoid issues with identical excerpts in different sectors
    df1['g'] = df1.groupby('Modified Excerpt').cumcount()
    df2['g'] = df2.groupby('Modified Excerpt').cumcount()

    # Merging keeps only identical execrpts (in True and Parsed)
    # For others sectors are not compared
    mm = df1.merge(df2, on=['Modified Excerpt','g'], suffixes=('','_p'))
    mm['lead'] = pp.lead

    # How many match and how many do not match
    nsec_ok  = (mm.DREF_Sector_id == mm.DREF_Sector_id_p).sum()
    nsec_bad = (mm.DREF_Sector_id != mm.DREF_Sector_id_p).sum()
    return nsec_ok, nsec_bad, mm[['position','Modified Excerpt','DREF_Sector_id','DREF_Sector_id_p','Learning','lead']]


# ****************************************************************************************
# Split Challenge-section into Challenges
# ****************************************************************************************

# ****************************************************************************************
# If smth strange i.e. 'and' just before the separator
def is_smth_strange(s1, s2, min_len = 10):
    strange_end = s1.rstrip(' ').split(' ')[-1] in ['and','the']
    too_short = (len(s2) < min_len) 
    # adding (len(s1) < min_len) breaks down some excerpts in ID015, VU008, not clear why
    return strange_end or too_short

def is_sentence_end(s, endings=['.', '?', '!']):
    s2 = strip_all_empty(s, left=False)
    if len(s2)==0:
        return False
    return s2[len(s2)-1] in endings   

# ****************************************************************************************
# If the first char is upper-case
def is_sentence_start(s):
    for i in range(len(s)):
        c = s[i]
        if c.islower() and (not c.isupper()):
            return 0
        if c.isupper() and (not c.islower()):
            if i+1>=len(s): 
                return 0 # One char is not a sentence
            if s[i+1].isupper() and (not s[i+1].islower()):
                # Two capital letters (abbreviation). 
                # Cannot tell if this is a sentence start
                return 0.5
            else:
                # Capital letter then small letter
                return 1
        if c in all_bullets: 
            # bullet point is like a start of sentence
            return 1
    # if no letters found - lower or upper - then it's not a sentence, hence not a sentence start
    return 0


# ****************************************************************************************
# replaces all separators by 0th separator and then splits
def split_by_seps(cc, seps):
    for sep in seps[1:]:
        cc = cc.replace(sep,seps[0])
    return cc.split(seps[0])

# ****************************************************************************************
# Returns text splitted by at least one of separators (but only if they separate sentences)
def split_text_by_separator(cc0, seps = ['\n\n'], bullets=['\n●','\n•','\n-']):
    splitted = []
    # replace other separators by 0th separator
    cc = cc0
    for sep in seps[1:]:
        cc = cc.replace(sep,seps[0])
    sep = seps[0]
    nsep = cc.count(sep)
    # Presence of bullets adds confidence that we should split
    splitted_by_bullets = split_by_seps(cc0, bullets)

    current_piece = cc.split(sep)[0]
    for i in range(nsep):
        
        # Separator is ok only if it looks like it separates sentences
        ends_ok   = is_sentence_end  (cc.split(sep)[i])
        starts_ok = is_sentence_start(cc.split(sep)[i+1])
        not_strange = not is_smth_strange(cc.split(sep)[i], cc.split(sep)[i+1])
        # if both fragment - after and before - coincide with fragments obtained
        # by splitting with bullets only, then it's likely to be correctly
        # splitted fragments:
        bullet_borders = ((cc.split(sep)[i  ] in splitted_by_bullets) + 
                          (cc.split(sep)[i+1] in splitted_by_bullets))
        sep_ok = ends_ok + starts_ok + not_strange + bullet_borders*0.5 >= 2
        if sep_ok:
            splitted.append(current_piece)
            current_piece = ''
        current_piece += cc.split(sep)[i+1]
    splitted.append(current_piece)     
    return splitted   

# If it looks like smth different, e.g. a typical heading,
# then it is not an excerpt
def reject_excerpt(cc):
    if cc.count('Output')>0 and has_digit_dot_digit(cc):
        # it is typical heading
        return True
    if cc.count('\nOutcome 1')>0 or cc.count('\nOutcome 2')>0:
        # it is typical heading
        return True
    return False

# ****************************************************************************************
# Loops over list and splits each element by separator(s)
# Possible extra_separators: "In addition,"  but it's not always separator.
def split_list_by_separator(chs, seps = ['\n\n','\n \n','\n  \n','\n   \n',
                            '\n●','\n•','\n-','\n2.','\n3.','\n4.','\n5.'], 
                            extra_sep=['\nOutput 1','\nOutput 2','\nOutcome 1','\nOutcome 2']):
    new_chs = []
    for ch in chs:
        cc = ch[1]
        for e in extra_sep:
            cc = cc.replace(e, seps[0]+e)
        splitted = split_text_by_separator(cc, seps = seps)

        # Drop all starting with an element that must be rejected
        for i,spl in enumerate(splitted):
            if reject_excerpt(spl):
                splitted = splitted[:i]
                break

        for spl in splitted:
            new_chs.append((ch[0],spl))
    return new_chs 

# ****************************************************************************************
# Locate & Process Challenges
# ****************************************************************************************

# Skip challenge when it is basically absent
def skip_ch(ch): 
    if len(ch)<3:
        return True
    if not exist_two_letters_in_a_row(ch):
        return True
    if strip_all(ch).startswith('None') and (len(ch)<30):
        return True
    if strip_all(ch).startswith('Nothing') and (len(ch)<30):
        return True
    if ch.startswith('No challenge') and (len(ch)<30):
        return True
    if ch.startswith('No lesson') and (len(ch)<30):
        return True
    if ch.startswith('Not applicable') and (len(ch)<30):
        return True
    if ch.strip(' ').strip('\n').strip(' ').strip('.').lower() in ['none', 'n/a']:
        return True
    if ch.startswith('Similar challenges as') and (len(ch)<70):
        return True
    if ch.strip(' ').strip('\n').strip('\t').startswith('Not enough reporting') and (len(ch)<105):
        return True
    return False

# ****************************************************************************************
# Splits CH (or LL) section into separate CHs, and cleans 
def split_and_clean_CHLL(chs):
    # Strip away extra symbols
    chs = [(ch[0], strip_all_empty(ch[1])) for ch in chs] 
    
    # Remove what looks like an image caption
    chs = [(ch[0], drop_image_caption(ch[1])) for ch in chs] 

    # Split into challenges (based mainly on double-linebreaks)
    chs = split_list_by_separator(chs)
    chs = [(ch[0], strip_all(ch[1])) for ch in chs] 

    # Remove "N/A" etc indicating absence of challenges
    chs = [ch for ch in chs if not skip_ch(ch[1])]

    # Remove too short ones
    chs = [ch for ch in chs if len(ch[1])>5]

    # Remove linebreaks (only single linbreaks are left)
    chs = [(ch[0], ch[1].replace('\n','')) for ch in chs]

    # Remove double spaces
    chs = [(ch[0], ch[1].replace('  ',' ').replace('  ',' ')) for ch in chs]
    return chs  

# In some cases a multiple linebreak means the end
# of Challenge section, e.g. if it contains 
# only "N/A-like" text
def stop_at_multiple_LBs(s0, stop='\n\n\n\n\n'):
    s = drop_spaces_between_linebreaks(s0)
    i = s.find(stop)
    if i<0: # 'stop' was not found
        return False
    s_before = s.split(stop)[0]
    s_after = s.split(stop)[1].split('\n\n')[0]
    NA_challenge = skip_ch(strip_all_empty(s_before))
    other_section_after = strip_all_empty(s_after).startswith('Strategies for Implementation') 
    #TODO: add other section names e.g. Health, see CU006
    return NA_challenge or other_section_after

# ****************************************************************************************
# extract Challenges from text
def get_CHs_from_text(txt):
    patterns = ['\n\nChallenges', '\n \nChallenges', '\n  \nChallenges', 
                '\nChallenges \n', '\n\n Challenges']
    keyword = '\nChallenges'
    
    chs = findall_patterns(patterns, txt, region=True, n=50000, nback=5, pattern2='\nLessons ') 
    
    # The approach below doesn't work so well because sometimes there are only 2 linebreaks between CHs and LLs
    #txt2 = drop_spaces_between_linebreaks(txt)   
    #chs = findall_patterns(patterns, txt2, region=True, n=2550, nback=0, pattern2='\n\n\n') 

    # Leave only text after the word "Challenges"
    #chs = [(ch[0], ch[1].split(keyword)[1]) for ch in chs] 
    chs = [(ch[0], ch[1][len(ch[1].split(keyword)[0])+len(keyword):]) for ch in chs]

    # We must stop the fragment at linebreaks if:
    # 1. CH fragments overlap (i.e. LL section is missing)
    # 2. fragment is too long
    # 3. fragment is quite long and likely to stop at LBs
    for i,ch in enumerate(chs):
        overlaps_next = (i+1 < len(chs)) and (ch[0] + len(ch[1]) > chs[i+1][0])
        too_long = len(ch[1])>3500
        quite_long = len(ch[1])>1000
        if overlaps_next or too_long or (quite_long and stop_at_multiple_LBs(ch[1])):
            chs[i] = (ch[0], finish_LL_section(ch[1], stop='\n\n\n\n'))
    
    chs = [(ch[0], avoid_pagebreak  (ch[1])) for ch in chs]
    chs = [ch for ch in chs if ch[1]!='']

    chs = split_and_clean_CHLL(chs)   
    return chs    

# ****************************************************************************************
# get PDF filename from lead: 
def get_PDFfilename_from_lead(lead, folder=''):
    if folder=='':  folder = all_pdf_folders

    if type(folder)==str:
        filenames = glob.glob(folder+"/"+lead+'*.pdf')
    else:
        filenames = []
        for f in folder:
            filenames += glob.glob(f+"/"+lead+'*.pdf')
    filenames = [f for f in filenames if f.count('_copy.pdf')==0]

    if len(filenames)>1:
        print('WARNING: more than 1 file for '+lead+': ', filenames)
    if len(filenames)==0:
        print('ERROR: No PDF files with name ', folder,"/"+lead+'*.pdf')
        sys.exit(-1)
    return filenames[0]

# get PDF text from lead (from disk or from API) 
def get_PDFtext_from_lead(lead, source='disk', folder='', method='tika'):

    if source=='disk':
        filename = get_PDFfilename_from_lead(lead, folder=folder)

        # Two methods to extract text, they give very similar results.
        # TODO: check which method is better
        if method == 'tika':
            txt = tika.parser.from_file(filename)['content'] 
        else:
            txt = pdfminer.high_level.extract_text(filename)        

    else:
        # source = 'api'.
        # can choose between 2 options:

        # Option 1
        #url = get_pdf_url(lead)
        #txt = tika.parser.from_file(url)['content'] 
        # Option 2
        pdf_io = get_pdf_io_object(lead)
        txt = tika.parser.from_buffer(pdf_io)['content'] 
    return txt


# ****************************************************************************************
# QC parsed Challenges
# ****************************************************************************************
# Builds a matrix on how 2 lists of strings match each other. Matrix elements:
# 3 - perfect match
# 2 - both strings start with the same substring of length n
# 1 - substring is contained in a string
def build_comp_matrix(chs_true, chs_parsed, n=30):
    matr = np.zeros((len(chs_true),len(chs_parsed)))
    for i in range(len(chs_true)):
        start = chs_true[i][:n]
        for j in range(len(chs_parsed)):
            # If start of true is contained in parsed (or viceversa)
            if chs_parsed[j].lower().count(start.lower())>0:
                matr[i,j] = 1
            if chs_true[i].lower().count(chs_parsed[j][:n].lower())>0:
                matr[i,j] = 1

            #else: print(start, ' ||| ', chs_parsed[j][:n])
            if chs_parsed[j][:n].lower() == chs_true[i][:n].lower():
                matr[i,j] = 2
            if chs_parsed[j].strip('.') == chs_true[i].strip('.'):
                matr[i,j] = 3                   
    return matr.astype(int)

# ****************************************************************************************
# For Excerpts.
# Creates a dictionary to characterize how two lists of strings match each other, 
# based on their mismatch-matrix
def assess_match(matr, verbose=1):
    
    # matrix dimensions
    nt = matr.shape[0] # true
    np = matr.shape[1] # parsed

    missed = []
    exact = []
    not_exact = []
    startT = []
    if np==0:
        missed = [i for i in range(nt)]
    else:
        for i in range(nt):
            if matr.sum(axis=1)[i] == 0: missed.append(i) # if ALL are zeros
            if matr.max(axis=1)[i] == 3: exact.append(i)
            if matr.max(axis=1)[i] != 3: not_exact.append(i)
            if matr.max(axis=1)[i] >= 2: startT.append(i)
    
    extra = []
    startP = []
    for j in range(np):
        if matr.sum(axis=0)[j] == 0: extra.append(j)
        if matr.max(axis=0)[j] >= 2: startP.append(j)

    return Munch(nt=nt, np=np, nexact=len(exact), n_notexact=len(not_exact), 
                 missed=missed, extra=extra, not_exact=not_exact, exact=exact)
                 #, startT=startT, startP=startP)

# Run assess match for excerpts and for sectors
def assess_match_all(pp):
    match = assess_match(pp.matr)
    nsec_ok, nsec_bad, mm = assess_match_sector(pp)
    match.nsec_ok  = nsec_ok
    match.nsec_bad = nsec_bad
    match.sec_mm = mm
    match.lead = pp.lead
    return match

# ******************************************************************
# Get Parsed CH & LL.
# source = api or disk
def get_CHLLs(lead='MDRCD028', Learnings=['CH','LL'], PDFextras=Munch(), 
              do_remove_footer=True, source='api', folder='', pdf_file = None):

    if pdf_file:
        # get text directly from bytes of PDF file
        txt = tika.parser.from_buffer(pdf_file)['content']
    else:
        # get text from lead (by downloading the corresponding PDF file first)
        txt = get_PDFtext_from_lead(lead, source=source, folder=folder) 
    
    if do_remove_footer:
        if not lead in PDFextras.keys():
            print(f'ERROR: Lead {lead} not in PDFextra')
            sys.exit(-1)
        txt = remove_footer(txt, PDFextras[lead])
        txt = remove_header(txt, PDFextras[lead])

    parsed = []
    if 'CH' in Learnings: parsed += [(ch[0], ch[1], 'Challenges'    ) for ch in get_CHs_from_text(txt)]
    if 'LL' in Learnings: parsed += [(ch[0], ch[1], 'Lessons Learnt') for ch in get_LLs_from_text(txt)]

    # Add section names
    secs = find_sections(txt)
    exs_parsed = [(ch[0], ch[1], ch[2], section_from_position(secs, ch[0])) for ch in parsed]
    exs_parsed = pd.DataFrame(exs_parsed, columns=['position','Modified Excerpt','Learning','section'])

    # Convert section name to full and short DREF_sector:
    exs_parsed['DREF_Sector_id'] = exs_parsed.section.apply       (lambda x: shorten_sector(x))
    exs_parsed['DREF_Sector']    = exs_parsed.DREF_Sector_id.apply(lambda x: full_sector_name(x))
    #del exs_parsed['section']

    exs_parsed['lead'] = lead
    return exs_parsed, parsed


# ****************************************************************************************
# Extract challenges (or LLs) and compare them to the true ones
# Learning='CH' or 'LL'
def get_CHs_and_compare(q, lead='MDRCD028', Learning='CH', PDFextras=Munch(), verbose=0, n=30, do_remove_footer=True, folder=''):

    LearningLong = Learning.replace('CH','Challenges').replace('LL','Lessons Learnt')

    exs_parsed, chs_parsed = get_CHLLs(lead=lead, Learnings=[Learning], PDFextras=PDFextras, 
                                       do_remove_footer=do_remove_footer, source='disk', folder=folder)
    
    q1 = q[q['Lead Title']==lead]
    chs_true = list(q1[q1.Learning==LearningLong]['Modified Excerpt'].unique())
    chs_true = [ch.replace('\n',' ') for ch in chs_true]
    chs_true = [ch.replace('  ',' ') for ch in chs_true] # since we do this replace in parsed
        
    # Excerpts with sectors
    exs_true = q1.groupby(by=['Modified Excerpt','DREF_Sector','Learning'], sort=False).count()[['Date']].reset_index()
    exs_true.rename(columns = {'Date':'count'}, inplace=True)
    exs_true['DREF_Sector_id'] = exs_true.DREF_Sector.apply(lambda x: shorten_sector(x))

    # Leave only text:
    chs_parsed = [ch[1] for ch in chs_parsed] 
    matr = build_comp_matrix(chs_true, chs_parsed, n=n)

    pp = Munch(lead=lead, matr=matr, chs_true = chs_true, chs_parsed=chs_parsed, 
               exs_true = exs_true, exs_parsed = exs_parsed)

    pp.echs_parsed = pp.exs_parsed # old names for backward compatibility
    return pp

# get_CHs_and_compare Modified: updates PDFextra first (if necessary)
def get_CHs_and_compareM(q, lead='MDRCD028', Learning='CH', PDFextras=Munch(), verbose=0, n=30, do_remove_footer=True, folder=''):
    PDFextras = get_PDFextras([lead], PDFextras, renew=False)
    pp = get_CHs_and_compare(q, lead=lead, Learning=Learning, PDFextras=PDFextras, 
                              verbose=verbose, n=n, do_remove_footer=do_remove_footer, folder=folder)
    return pp, PDFextras

# ****************************************************************************************
# Read PDFs from folder (excludes duplicates named *_copy.pdf)
def read_pdfs_from_folder(folder='../data/PDF'):
    pdfs = glob.glob(folder + "/MD*")
    pdfs = [pdf for pdf in pdfs if pdf.count('_copy.pdf')==0]
    pdfs = pd.DataFrame({'name':pdfs})    
    pdfs['title'] = pdfs.name.apply(lambda x: x.split(folder+'\\')[1].split('.')[0])
    pdfs['lead'] = pdfs.title.apply(lambda x: x[:8])
    pdfs['ext'] = pdfs.title.apply(lambda x: x[8:])
    return pdfs

# Get leads that are both (1) in PDF folder and (2) in dataset
def get_pdf_names(q, folder='../data/PDF-2020'):
    
    pdfs = read_pdfs_from_folder(folder=folder)
    leads_given = set(pdfs.lead.values)

    # Read dataset leads
    leads_dataset = set(q['Lead Title'].unique())
    pdfs['in_dataset'] = pdfs.lead.apply(lambda x: x in list(leads_dataset))
    pdfs['country'] = pdfs.lead.apply(lambda x: x[3:5])
    vc = q[['Lead Title','Date']].value_counts().reset_index()
    pdfs_merged = vc.merge(pdfs, left_on='Lead Title', right_on='lead', how='inner')
    return pdfs_merged

# Get leads that are (1) in dataset (2) 2020-2021 (3) Not included in IFRC upload
def get_PDF_names_fresh(q):
    pdfs_IFRC2020 = get_pdf_names(q, folder='../data/PDF-2020')
    leads_IFRC2020 = list(pdfs_IFRC2020.lead.values)
    pdfs_API = get_pdf_names(q, folder='../data/PDF-API')

    pdfs_API2020 = pdfs_API[pdfs_API.Date.apply(lambda x: x[:4]=='2020')]
    leads_API2020 = list(pdfs_API2020.lead.values)
    new_leads_API2020 = [lead for lead in leads_API2020 if not lead in leads_IFRC2020]

    pdfs_down2021 = get_pdf_names(q, folder='../data/PDF-download-2021')
    leads_down2021 = list(pdfs_down2021.lead.values)

    pdfs_down2020 = get_pdf_names(q, folder='../data/PDF-download-2020')
    leads_down2020 = list(pdfs_down2020.lead.values)
    return new_leads_API2020 + leads_down2021 + leads_down2020

#############################################################################################
# LESSONS LEARNED
#############################################################################################

# Find where LL section starts, i.e. strip away its title (smth like 'Lessons Learned:\n')
# We use one linebreak as pattern, to be safe, even though in 99% of cases
# there is a double-linebreak after 'Lessons Learned'
def strip_LL_section_start(s, start =  '\nLessons', pattern='\n'):
    tmp = drop_spaces_between_linebreaks(s.lstrip(start))
    # text between '\nLessons' and first linebreak:
    before_LB = tmp.split(pattern)[0]
    before_LB_strip = before_LB.strip(' ').strip(':').strip(' ')

    # OK section start means 'learned' or 'learnt' after 'Lessons'
    is_section_start_ok = before_LB_strip.lower() in ['learned', 'learnt']
    if is_section_start_ok:
        return tmp.lstrip(before_LB).lstrip(pattern)
    else:
        return ''

# LL section ends when we meet several linebreaks at once.
# With some exceptions.
def finish_LL_section(s, stop='\n\n\n'):
    s2 = drop_spaces_between_linebreaks(s)
    s2 = s2.lstrip('\n')    
    ss = s2.split(stop)
    # Often we stop at the first LBs
    output = ss[0]
    if len(ss)==1: #(especially if there's nothing after it)
        return output
    else:
        # remove empty splits
        ss = [s for s in ss if s!='']

    # This gives us the bullet type at the start (or '' if starts not with a bullet)
    bullet = starts_with_bullet(ss[0])

    for i in range(1,len(ss)):
        if bullet != '':
            # if LL section started with a bullet
            if starts_with_bullet(ss[i], bullets=[bullet]) != '' :
                # if we meet the same bullet, it must be continuation of LL section
                output += stop + ss[i] 
                continue 
        after_stop_before_LB = ss[i].split('\n')[0]
        # LL section is sometimes divided into subsections with typical title
        if strip_all_empty(after_stop_before_LB) == 'Recommendations':
            # we skip this title word and continue LL section
            skip_symbols = len(after_stop_before_LB)
            output = output + stop + ss[i][skip_symbols:]
            continue
        # If ends with ':', it's not the end of LL section
        if strip_all_empty(output, left=False).endswith(":"):
            output += stop + ss[i] 
            continue 

        break # if no special reason to continue, then we stop LL section 

    # Should stop at least at Challenge section 
    # (if we came that far, it is a sign that LL section must be shortened even more)
    output = output.split('\nChallenges')[0] 
    return output

# If we have a list item with only capital letters,
# this element and all sunsequent elements are excluded
# (capital letters means it's a section title rather than LL)
def stop_at_capital(lls):
    lls_new = []
    for ll in lls:
        if ll[1].upper() == ll[1]:
            break
        lls_new.append(ll)
    return lls_new

# Finds LL-section from the text    
def get_LLs_from_text(txt):
    pattern0 = '\nLessons'
    lls = findall_patterns(pattern0, txt, region=True, n=7000, nback=0)
    lls = [(ll[0], strip_LL_section_start(ll[1])) for ll in lls]
    lls = [(ll[0], avoid_pagebreak       (ll[1])) for ll in lls]
    lls = [(ll[0], finish_LL_section     (ll[1])) for ll in lls]
    lls = [ll for ll in lls if ll[1]!='']

    lls = split_and_clean_CHLL(lls) 
    lls = stop_at_capital(lls)
    return lls    


#############################################################################################
# ADVANCED PDF HANDLING
#############################################################################################

# Selects the first and last elements from each page:
# They are presumable header and footer.
# Also, postheader - what comes after header.
def get_header_footer_candidates(filename = "../data/PDF-2020/MDRCD030dfr.pdf"):
    headers = []
    footers = []
    postheaders = []
    for page_layout in extract_pages(filename):
        postheader_now = False
        header_now = True
        for element in page_layout:
            if isinstance(element, LTTextContainer):
                # ignoring empty elements
                if strip_all_empty(element.get_text()) != '':
                    element_text = element.get_text()
                    if postheader_now:
                        postheader = element_text
                        postheader_now = False
                    if header_now:
                        header = element_text
                        header_now = False
                        postheader_now = True

        footer = element_text
        headers.append(header)
        postheaders.append(postheader)
        footers.append(footer)
    return headers, footers, postheaders    

#***************************************************************
# Returns substring preceeding a number
def before_number(s):
    for i in range(len(s)):
        if is_digit(s[i]):
            return s[:i]
    return s

# Returns substring after a number
def after_number(s):
    for i in range(len(s)-1,-1,-1): 
        if is_digit(s[i]):
            return s[i+1:]
    return s

# Does it have substrings like '1.5', typical for section numbers
def has_digit_dot_digit(s):
    for i in range(len(s)-2):
        if is_digit(s[i]):
            if (s[i+1]=='.') and is_digit(s[i+2]):
                return True
    return False

#***************************************************************
# Out of many footer-candidates (which are simply the last text elements on a page)
# finds one that repeats more than threshold 
def repeatable_element(footers0, threshold=0.5, numbers=''):
    
    if numbers == '':
        footers = footers0
    if numbers == 'stop_before':
        footers = [before_number(f) for f in footers0]
    if numbers == 'stop_after':
        footers = [after_number(f) for f in footers0]
        
    vc = pd.DataFrame({'footer':footers}).footer.value_counts()
    if vc[0] > threshold * len(footers):
        return vc.index[0].rstrip('\n')
    else:
        return ''

#***************************************************************
# Footers or headers may include page number. This function figures out whether they do
# and identifies the most repeatable footer(header) ignoring occasional varying page number.
# Threshold 0.3 means that a text is decided to be a footer if it occurs at the bottom of at least 30% of pages
def repeatable_element_auto(footers0, threshold=0.3):
    output1 = repeatable_element(footers0=footers0, threshold=threshold, numbers='')
    output2 = repeatable_element(footers0=footers0, threshold=threshold, numbers='stop_before')
    output3 = repeatable_element(footers0=footers0, threshold=threshold, numbers='stop_after')
    if len(output1)>len(output2) and len(output1)>len(output3):
        return output1 
    else:
        return output2 if len(output2)>len(output3) else output3

# ***********************************************************
# Removes footers from the text, replaces them by pbflag.
# Footers may include nearest symbols up to (or only) linebreaks+spaces
# TODO add comment???
def cut_footers(txt, footer, n=300, after='', before=''):

    if len(footer)<=1: return txt
  
    txt_out = txt
    cc = findall(footer, txt, region=True, n=n, ignoreCase=False)
    # Loop over footers, start from the end so that indices are not changed
    # when later footers are removed
    for c in cc[::-1]:
        s = c[1]; k=c[0]
        
        # Search backwards from footer
        i = k
        if before == 'drop_linebreaks':
            # extend footer with nearest 'empty' characters
            while txt[i-1] in [' ','\n']:
                i = i - 1
                if i==0: break
        if before == 'stop_at_linebreak':
            # extend footer until a linebreak is found
            while not txt[i-1] in ['\n']:
                i = i - 1
                if i==0: break
        start = i
        
        # Search forward from footer, the same 2 options
        i = k + len(footer)
        if after == 'drop_linebreaks':
            while txt[i] in [' ','\n']:
                i = i + 1
                if i==len(txt): break
        if after == 'stop_at_linebreak':
            while not txt[i] in ['\n']:
                i = i + 1
                if i==len(txt): break
        finish = i
        #print(start, finish)
        txt_out = txt_out[:start] + pbflag + txt_out[finish:]
        #txt_out = txt_out[:start] + '' + txt_out[finish:]
    
    return txt_out         

# ************************************************************************
# In the text the header is often preceeded by linebreaks.
# Let's include them in the header if they are present for all pages
def extend_header_with_linebreaks(header, txt):

    cc = findall(header, txt, region=True, n=30, ignoreCase=False)    
    
    lbs = [] # how many linebreaks preceed the header at each page
    for c in cc:
        k=c[0]

        i = k
        while txt[i-1] in ['\n']:
            i = i - 1
            if i==0: break
        lbs.append(k-i)   
    # Choose the minimum number over all pages
    header_new = min(lbs)*'\n' + header
    return header_new
    
# ************************************************************************
# For Footer and Header:
# Determine it by finding most repeatable item from page to page.
# Remove it, i.e. replace by a pagebreak flag
def remove_footer(txt, PDFextra):
    footer = repeatable_element_auto(PDFextra.footers)
    #footer = extend_header_with_linebreaks(footer, txt)
    return cut_footers(txt, footer, n=300, 
                       before = 'stop_at_linebreak', after = 'stop_at_linebreak')           

def remove_header(txt, PDFextra):
    header = repeatable_element_auto(PDFextra.headers)
    #header = extend_header_with_linebreaks(header, txt)
    return cut_footers(txt, header, n=300, 
                       before = 'stop_at_linebreak', after = 'stop_at_linebreak')           

# ************************************************************************
# Load PDFextras for all leads where it's missing.
# Keep existing values if renew=False.
# (Makes sense since it takes long time to process all PDFs)
def get_PDFextras(leads, PDFextras, renew=False, source='disk', folder='', pdf_file = None):
    for lead in leads:
        if renew or (not lead in PDFextras.keys()):
            # get pdf_io which is either filename or a file-like object
            if pdf_file:
                # if pdf_file (as bytes) is given:
                pdf_io = io.BytesIO(pdf_file)
            else:
                # otherwise, read pdf file from disk, or download
                if source=='disk':
                    pdf_io = get_PDFfilename_from_lead(lead, folder=folder)
                else:
                    pdf_io = get_pdf_io_object(lead) # IO object with PDF data
            headers, footers, postheaders  = get_header_footer_candidates(filename = pdf_io)
            PDFextras[lead] = Munch(headers = headers, footers=footers, postheaders = postheaders)
    return PDFextras    


# ************************************************************************
# Helper functions for avoid_pagebreak
def remove_double_pbflag(c):
    splits = c.split(pbflag)
    splits_new = []
    for split in splits:
        if strip_all_empty(split)!='':
            splits_new.append(split)
    return pbflag.join(splits_new)  

# TODO: other bulets ???
def is_same_bullet_type(c1, c2):
    c2 = strip_all_empty(c2, right=False)
    bullet = '• '
    if c1.startswith(bullet) and c2.startswith(bullet):
        return True
    return False

#************************************************************************
# Removes pagebreaks identified by a flag.
# Joins the text on the next page if it looks like it's a continuation
# of the previous page
def avoid_pagebreak(c, stop='\n\n\n'):
    # Replaces possible double flags (from both header & footer) by one flag
    c = remove_double_pbflag(c)

    if c.count(pbflag)==0:
        # if no pagebreaks, do nothing
        cout = c

    else:
        c1 = c.split(pbflag)[0]
        c2 = c.split(pbflag)[1]
        if strip_all_empty(c1).count(stop)>0:
            # stops are found before pagebreak, hence ignore the next-page text
            cout = c1
        else:
            consistent = is_sentence_end(c1) == is_sentence_start(c2)
            must_go_on = strip_all_empty(c1, left=False)[-1]==':'
            # NB: so far must_go_on is never used, i.e. can be dropped
            if consistent or must_go_on or c1=='':
                # Looks like next-page text may be a continuation of previous-page
                # Thus, we shall append the next-page text
                if is_same_bullet_type(c1, c2):
                    # the same bullets used before and after, hence it's likely
                    # the same block of text, thus lets remove linebreaks coming from the pagebreak
                    c1 = strip_all_empty(c1, left=False)
                    c2 = strip_all_empty(c2, right=False)
                cout = c1 + '\n\n' + c2
            else:
                cout = c1
    return cout    

#*********************************************************************************************
# Remove a piece of text that presumable is an image caption because it contains 'pattern"
def drop_image_caption_one(a, pattern = '(Photo:'):
    if a.count(pattern)==0:
        return a
    # Find where the pattern occurs, and the caption ends
    i0 = findall(pattern, a)[0][0]
    if a[i0:].count('\n\n')==0:
        end_caption = len(a)
    else:
        end_caption = i0 + findall('\n\n', a[i0:])[0][0]
    
    # Search for double linebreaks backwards.
    # Choose those that are followed by a sentence start.
    # It gives the start of the caption
    dlbs = findall('\n\n', a[:i0])
    start_caption = 0
    for dlb in dlbs[::-1]:
        txt_after_dlb = a[dlb[0]:][:20]
        if is_sentence_start(txt_after_dlb):
            start_caption = dlb[0]
            break
    return a[:start_caption] +  a[end_caption:]

#*********************************************************************************************
# Removes a piece of text that presumably is an image caption 
# because it contains one of 'patterns"
def drop_image_caption(a, patterns = ['(Photo:', '(Image:', 'Source:'] ):
    for patt in patterns:
        a = drop_image_caption_one(a, pattern = patt)
    # Do it again, in case there are two captions 
    for patt in patterns:
        a = drop_image_caption_one(a, pattern = patt)
    return a

# Find a year for a lead, PDF is read from disk
def leads_year(folder = '../data/PDF/', year='all'):
    drefs0 = pd.read_csv(folder + '/drefs.csv')
    drefs = drefs0[drefs0.lead!='Unknown'].reset_index(drop=True)
    drefs['year'] = drefs.created_at.apply(lambda x: int(x[:4]))
    if year=='all':
        return drefs.lead.values
    else:
        return drefs[drefs.year==year].lead.values