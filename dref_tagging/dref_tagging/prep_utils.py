import pandas as pd
import os
import time
from importlib import resources
from fuzzywuzzy import process as fuzzywuzzy_process

# Short codes for 5 DREF Dimensions:
dim_code = {'Policy, Strategy and Standards':'1-PSS',
            'Analysis and Planning':'2-AP',
           'Operational Capacity':'3-OC',
           'Coordination':'4-C',
           'Operations Support':'5-OS'}


# ------------------------------------------------------------------
# Preliminary cleaning of Ops Learning dataset
def clean_learning_dataset(q):

    # Shorten column names
    for c in q.columns:
        if c.startswith('DREF'):
            q = q.rename(columns={c:'DREF_'+c.split(' ')[-1]})   
            
    # Removing columns that are NaNs except a few typos
    cols_to_remove = ['Original Excerpt','Information date','DREF_Subsectors']
    for c in cols_to_remove:
        if c in q.columns:
            del q[c]

    # Removing 6 rows where important columns are missing
    # NB: removing them creates some problems when testing PDF parsing
    q = q.dropna(subset=['DREF_Dimension']) # 4 rows, 2020/2021
    q = q.dropna(subset=['Learning']) # 2 rows from 2017
    
    return q.reset_index(drop=True)


# Read the raw dataset, clean and save it
def clean_and_save_dataset(filename_in  = 'Ops_learning_Dataset.csv', 
                           filename_out = 'Ops_learning_Dataset_clean.feather'):

    with resources.path("dref_tagging.config", filename_in) as input_file:
        q = pd.read_csv(input_file)

    q = clean_learning_dataset(q)

    # save the file (to the same folder as input)
    full_filename_out = os.path.join(os.path.dirname(input_file), filename_out)

    if os.path.splitext(filename_out)[1] == '.feather':
        q.to_feather(full_filename_out)
    else:
        # must be csv
        q.to_csv(full_filename_out)
    return 

# ------------------------------------------------------------------
# Read PER Guide that has a numbered list of all DREF Subdimensions:
# extract their names and numbers and return as a df
def read_DREF_PER_Guide(filename = "DREF_PER_Guide.txt"):

    # read the file
    with resources.path("dref_tagging.config", filename) as input_file:
        fileObject = open(input_file, "r") 
        txt = fileObject.read()
    
    # Description of each Subdimension starts with the word 'Component'
    fragments = txt.split('Component')
    # Text fragment before the first occurrence of 'Component' can be ignored
    fragments = fragments[1:]

    # Create a df with names and numbers for components
    nums = []
    comps = []
    for fragment in fragments:
        num = fragment.split(' ')[1]
        comp = fragment.split(':')[1].split("\n")[0]
        nums.append(num)
        comps.append(comp)

    df = pd.DataFrame({'number':nums, 'Subdimension':comps})

    # Drop irrelevant symbols
    df.number = df.number.apply(lambda x: x.rstrip(':'))
    for i in range(5):
        df.Subdimension = df.Subdimension.apply(lambda x: x.rstrip(' '))
        df.Subdimension = df.Subdimension.apply(lambda x: x.rstrip('.'))
        df.Subdimension = df.Subdimension.apply(lambda x: x.lstrip(' '))

    df.Subdimension = df.Subdimension.apply(lambda x: x.lower())
    df.Subdimension = df.Subdimension.apply(lambda x: x.replace('cash based intervention','cash and voucher assistance'))
    df.Subdimension = df.Subdimension.apply(lambda x: x.replace('disaster risk management laws','drm laws'))
    return df


# -----------------------------------------------------------------------------------
# Help-function used in match_subdimension_names:
# it finds the best matches between columns 'name' and a list of names 
def match_two_columns(subdims_df, names_to_match, suffix='_in_data'):
    subdims_df['name'+suffix] = ''
    subdims_df['match'+suffix] = ''
    for i in range(len(subdims_df)):
        matching_name = fuzzywuzzy_process.extractOne(subdims_df.name[i].lower(), names_to_match)
        subdims_df.loc[i,'name'+suffix] = matching_name[0]
        subdims_df.loc[i,'match'+suffix] = matching_name[1]
        names_to_match.remove(matching_name[0])
    return subdims_df

# -----------------------------------------------------------------------------------
# Read Subdimension names from 3 sources: from dataset, from a list of 'true' names, 
# and from a guide where names also come with numbers.
# Match them all to each other by similarity metric from fuzzywuzzy.
# Assign also DREF-code
def match_subdimension_names(subdimension_list='subdimensions_list-2021-12.txt',
                             dataset = 'Ops_learning_Dataset.feather',
                             DREF_PER_Guide = "DREF_PER_Guide.txt",
                             tags_dict_original = 'tags_dict_original.csv'):

    # read the subdimension list and the dataset
    with resources.path("dref_tagging.config", subdimension_list) as input_file:
        subdims_df = pd.read_csv(input_file, sep='\t', header=None, names=['name'])
    with resources.path("dref_tagging.config", dataset) as input_file:
        if os.path.splitext(dataset)[1]=='.feather':
            q = pd.read_feather(input_file)
        else:
            q = pd.read_csv(input_file)
    
    # read tags-disctionary + some preprocessing
    with resources.path("dref_tagging.config", tags_dict_original) as input_file:
        tags_dict = pd.read_csv(input_file)
    tags_dict.rename(columns={'Unnamed: 0':'id'}, inplace=True)
    tags_dict.Category = tags_dict.Category.apply(lambda x: x.lower())
    tags_dict.Category = tags_dict.Category.apply(lambda x: x.replace('cash based intervention','cash and voucher assistance'))
    tags_dict.Category = tags_dict.Category.apply(lambda x: x.replace('disaster risk management laws','drm laws'))

    # get all names of subdimensions in the dataset & merge by similar names
    q['DREF_Subdimension_lower'] = q.DREF_Subdimension.apply(lambda x: x.lower())
    subdims_names_in_data = list(set(q.DREF_Subdimension_lower.unique()))
    subdims_df = match_two_columns(subdims_df, subdims_names_in_data, suffix='_in_data') 

    # get all names of subdimensions in the DREF guide & merge by similar names
    guide = read_DREF_PER_Guide(filename = DREF_PER_Guide)
    subdims_names_in_guide = list(guide.Subdimension.unique())
    subdims_df = match_two_columns(subdims_df, subdims_names_in_guide, suffix='_in_guide') 

    subdims_names_in_tags = list(tags_dict.Category.unique())
    subdims_df = match_two_columns(subdims_df, subdims_names_in_tags, suffix='_in_tags')
    subdims_df = subdims_df.merge(tags_dict[['id','Category']], left_on='name_in_tags', right_on='Category')

    # Get 'number' column from guide-df
    subdims_df = subdims_df.merge(guide, left_on='name_in_guide', right_on='Subdimension')
    del subdims_df['Subdimension']

    # Take Dimension for each Subdimension from OpsL dataset
    gb = q.groupby(by='DREF_Subdimension_lower')[['DREF_Dimension']].first().reset_index()
    # Get 'dimension' column from dataset:
    subdims_df = subdims_df.merge(gb, left_on='name_in_data', right_on='DREF_Subdimension_lower', how='left')

    # Add DREF code (based on Dimension and Subdimension):
    subdims_df['num'] = subdims_df.number.apply(lambda x: int(x[:-1]) if len(x)==3 else int(x))
    subdims_df['DREF_DimCode'] = subdims_df.DREF_Dimension.map(dim_code)
    subdims_df['DREF_DimCode'] = subdims_df['DREF_DimCode'] + '.' + subdims_df.number.apply(lambda x: x[:-1]+'-'+x[-1:] if len(x)==3 else x)
    subdims_df.sort_values(by=['num','DREF_DimCode'], inplace=True)

    return subdims_df

# ----------------------------------------------------------------------------------------------------
# Finalizes preprocessing. 
# Outputs 2 files: preprocessed dataset & subdimension list (DREF spec), 
# both - with codes and correct names for subdimensions/dimensions
def fix_names_and_codes_in_dataset(subdims_df, 
                                    dataset_clean_in = 'Ops_learning_Dataset_clean.feather',
                                    dataset_out = 'Ops_learning_Dataset_ready.feather',
                                    tags_dict_out='tags_dict.csv'):

    with resources.path("dref_tagging.config", dataset_clean_in) as input_file:
        if os.path.splitext(dataset_clean_in)[1]=='.feather':
            q = pd.read_feather(input_file)
        else:
            q = pd.read_csv(input_file)

    # Merge dataset with df holding correct names for Dimensions/Subdimensions & codes
    q['DREF_Subdimension_lower'] = q.DREF_Subdimension.apply(lambda x: x.lower())
    q = q.rename(columns={'DREF_Dimension':'DREF_Dimension_in_data'})
    cols_added = ['name','name_in_data','DREF_DimCode','DREF_Dimension']
    q = q.merge(subdims_df[cols_added], left_on='DREF_Subdimension_lower', right_on='name_in_data', how='left')

    # remove/rename columns
    cols_delete = ['DREF_Dimension_in_data', 'DREF_Subdimension', 'DREF_Subdimension_lower', 'name_in_data']
    for c in cols_delete:
        del q[c] 
    q = q.rename(columns = {'name':'DREF_Subdimension'})
    # remove columns
    cols_to_remove = [c for c in q.columns if c.startswith('Unnamed')]
    for c in cols_to_remove:
        del q[c]
    # reorder columns
    cols = list(q.columns)
    q = q[cols[:3]+cols[-3:]+cols[3:-3]]
    # save (to both csv and feather)
    output_filename = os.path.join(os.path.dirname(input_file), dataset_out)
    try:
        q.to_feather(os.path.splitext(output_filename)[0]+'.feather')
    except:
        print('WARNING: Failure to save FEATHER file, thus saving only CSV')
    q.to_csv    (os.path.splitext(output_filename)[0]+'.csv')

    # Save tags_dict 
    df_save = subdims_df.copy()
    df_save = df_save.rename(columns={'name':'Subdimension', 'DREF_Dimension':'Dimension', 'num':'Subdim_digits'})
    df_save = df_save.sort_values(by='id')
    cols = ['id','DREF_DimCode', 'Dimension', 'Subdimension','Subdim_digits']
    df_save = df_save[cols].set_index('id') 
    # One column must be copyied with a different name for backward compatibility
    df_save['Category'] = df_save['Subdimension']
    df_save.to_csv(os.path.join(os.path.dirname(input_file), tags_dict_out))
    # Identical file is also saved as 'DREF_spec.csv' since some functions use this name
    # TODO: drop this file and use tags_dict instead
    df_save.to_csv(os.path.join(os.path.dirname(input_file), 'DREF_spec.csv'))

    return

# ---------------------------------------------------------------------------------------
# Does all preprocessing actions. 
# Dataset and DREF-spec are saved to files
def preprocess_DREF_dataset(dataset_in = 'Ops_learning_Dataset.csv',
                            subdimensions_list_in = 'subdimensions_list-2021-12.txt',
                            DREF_PER_Guide_in = "DREF_PER_Guide.txt",
                            tags_dict_original_in = 'tags_dict_original.csv',

                            dataset_out = 'Ops_learning_Dataset_ready.feather',
                            tags_dict_out='tags_dict.csv'):
    
    dataset_tmp =  'Ops_learning_Dataset_tmp.csv'

    clean_and_save_dataset(filename_in  = dataset_in, 
                           filename_out = dataset_tmp)
    
    subdims_df = match_subdimension_names(subdimension_list = subdimensions_list_in,
                                          dataset = dataset_tmp,
                                          DREF_PER_Guide = DREF_PER_Guide_in,
                                          tags_dict_original = tags_dict_original_in)   

    fix_names_and_codes_in_dataset(subdims_df, 
                                   dataset_clean_in = dataset_tmp,
                                   dataset_out = dataset_out,
                                   tags_dict_out = tags_dict_out)
    return                                                                           