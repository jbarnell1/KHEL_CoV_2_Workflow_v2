from ..workflow_obj import workflow_obj
from ..reader import get_pandas, read_txt # TODO get_pandas no longer needed
from ..ui import get_path
from ..formatter import add_cols, format_hsn_col
import datetime
import cx_Oracle as co
import pandas as pd
from logger import Script_Logger
import json



class WorkflowObj1(workflow_obj):
    # constructor
    def __init__(self): #self helps python know its part of that class
        self.id = "WF_1"
        self.log= Script_Logger("WF1_Import_Demos")
        self.log.start_log("Initialization of WF_1_sucessful")

    # methods
    def get_json(self):
        super().get_json(1)
        self.log.write_log("get_json","Argument pass was 1")


    def get_priority(self):
        self.log.write_log("get_priority","Getting list of priority samples")
        lines = read_txt(self.priority_path)
        self.priority_lst = [line.strip("* \n") for line in lines]
        
        self.log.write_log("get_priority"," Done!")

    def verify_ctrls(self):
        if self.include_controls:
            today = datetime.datetime.today()
            self.log.write_log("verify_ctrls","Verifying control expiration dates")
            if datetime.datetime.strptime(self.pos_ctrl_exp, "%Y-%m-%d") <= today:
                self.log.write_warning("verfiy_ctrls","ALERT!! The positive control is out of spec!  Please update in data/private_cache.json")
                raise ValueError("Positive Control is invalid- already expired")
            if datetime.datetime.strptime(self.neg_ctrl_exp, "%Y-%m-%d") <= today:
                self.log.write_warning("verify_ctrls","ALERT!! The negative control is out of spec!  Please update in data/private_cache.json")
                raise ValueError("Positive Control is invalid- already expired")
            self.log.write_log("verify_ctrls","Done!")
        else:
            pass


    def get_initial_demo_df(self, runId_helper):
        self.log.write_log("get_intital_demo_df","Getting HSN from run_data.json")
        
        # TODO use run_data keys => list of HSNs, then make df from that
        # column name = 'Sample ID'
        self.log.write_log("get_intial_demo_df","opening json file and dumping HSNs into var")
        #get HSN from json
        hsn = [*json.load("//data/run_data.json")[runId_helper]]
    #check with jonathan
        self.log.write_log("get_intial_demo_df","Creating DF with only HSNs")

        self.df_right = pd.DataFrame(hsn)
        self.df_right.columns(["Sample ID"]) #is this called hsn or sample ID????
        '''
        self.demo_path = get_path()
        self.df_right = get_pandas(self.demo_path, 'WF_1', 'run order', ',')
        self.df_right = self.df_right.applymap(str)
        # drop controls from index
        neg = False
        pos = False
        for row in range(len(self.df_right.index)):
            if "neg" in self.df_right['Sample ID'][row].lower():
                neg_idx = row
                neg = True
            if "pos" in self.df_right['Sample ID'][row].lower():
                pos_idx = row
                pos = True
            if neg and pos:
                break
        if neg:
            self.df_right.drop([neg_idx], inplace=True)
        if pos:
            self.df_right.drop([pos_idx], inplace=True)'''


    def format_demo_df(self):
        #will need to check if this is still needed
        self.log.write_log("format_demo_df","Formating HSNs")
        self.df_right = format_hsn_col(self.df_right, hsn_colname='Sample ID', hsn_only=True)
        

    def get_initial_lims_df(self):
        # establish connection
        self.log.write_log("get_intital_lims_df","Establishing database connection")
        conn = co.connect(self.lims_conn)
        self.log.write_log("get_intital_lims_df","Succesful database connection")
       

        # query the database
        self.log.write_log("get_intital_lims_df","Querying database")
        
        hsn_lst = list(self.df_right['hsn']) #this might need to be update to new name
        valid_hsn_lst = []
        for item in hsn_lst:
            try:
                item = int(item)
                valid_hsn_lst.append(str(item))
            except:
                pass
        hsn_lst_query = "(" + ",".join(valid_hsn_lst) + ")"
        query = "select * from wgsdemographics where HSN in " + hsn_lst_query
        self.log.write_log("get_intital_lims_df","querying lims with query "+query)
        self.df = pd.read_sql(query, conn)
        conn.close()
        self.log.write_log("get_intital_lims_df","querying lims done")
        


    def format_lims_df(self):
        # manipulate sql database to format accepted by the master EXCEL worksheet
        self.log.write_log("format_lims_DF","Manipulating demographics to database format")
        self.df = self.df.rename(columns = self.demo_names)
        self.df["hsn"] = self.df.apply(lambda row: str(row["hsn"]), axis=1)
        self.log.write_log("format_lims_DF","Done!")
        

    def merge_dfs(self):
        self.log.write_log("merge_dfs","Merging dataframes")
        self.df = pd.merge(self.df, self.df_right, how="right", on="hsn")
        self.log.write_log("merge_dfs","Done")
        


    def format_dfs(self):
        self.log.write_log("format_dfs","Starting")
        # get the date for wgs_run_date column
        path_arr = self.demo_path.split("/")
        name = path_arr[-1]
        date_input = name[3:5] + "-" + name[5:7] + "-20" + name[7:9]
        self.wgs_run_date = datetime.datetime.strptime(date_input, '%m-%d-%Y')
        self.wgs_run_date = self.wgs_run_date.strftime("%m/%d/%Y")
        # format columns, insert necessary values
        self.log.write_log("format_dfs","Adding/Formatting/Sorting columns")

        self.df = add_cols(obj=self, \
            df=self.df, \
            col_lst=self.add_col_lst, \
            col_func_map=self.col_func_map)

        # sort/remove columns to match list
        self.df = self.df[self.sample_data_col_order]
        self.log.write_log("format_dfs","Done")
        

    def database_push(self):
        self.log.write_log("database_push","Starting")
        super().setup_db()
        df_demo_lst = self.df.values.astype(str).tolist()
        df_table_col_query = "(" + ", ".join(self.df.columns.astype(str).tolist()) + ")"
        self.write_query_tbl1 = self.write_query_tbl1.replace("{df_table_col_query}", df_table_col_query)
        self.db_handler.lst_ptr_push(df_lst=df_demo_lst, query=self.write_query_tbl1)
        self.log.write_log("database_push","Done!`")




