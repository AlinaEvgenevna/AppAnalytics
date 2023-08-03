#import

from datetime import datetime, timedelta
import pandas as pd
from io import StringIO
import requests

import pandahouse as ph

from airflow.decorators import dag, task
from airflow.operators.python import get_current_context



connection_from = {
    'host': '***',
    'password': '***',
    'user': '***',
    'database': '***'
}


connection_to = {'host': '***',
                      'database':'***',
                      'user':'***', 
                      'password':'***' 
}



# Дефолтные параметры
default_args = {
    'owner': 'a-ananchenko-20',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2023, 7, 7),
}

# Интервал запуска DAG
schedule_interval = '@daily'

@dag(default_args=default_args, schedule_interval=schedule_interval, catchup=False)
def dag_ananchenko():

    @task()
    def extract1():
        query = '''
                 SELECT user_id, event_date, 
                        if(gender=0, 'male', 'female') as gender, 
                        age, os, 
                        likes, views

                FROM

                (select distinct(user_id), gender, age, os
                 from {db}.feed_actions) t1

                JOIN

                (select user_id, 
                        countIf(action='like') AS likes,
                        countIf(action='view') AS views,
                        toDate(time) as event_date
                from {db}.feed_actions 
                WHERE toDate(time) = yesterday() 
                GROUP BY user_id, event_date) t2

                USING(user_id)


                '''
        df_cube1 = ph.read_clickhouse(query, connection = connection_from)
        return df_cube1

    
    
    @task()
    def extract2():
        query = '''
                SELECT user_id,
                event_date, 
                age, gender, os,
                messages_received, 
                messages_sent,
                users_sent,
                users_received

                FROM 

               (SELECT user_id, 
                event_date,      
                messages_received, 
                messages_sent,
                users_sent,
                users_received

                FROM 

               (select user_id, 
                       count(reciever_id) AS messages_sent,     
                       count(distinct(reciever_id)) AS users_sent,
                       toDate(time) as event_date
                       from {db}.message_actions
                       WHERE toDate(time) = yesterday() 
                       GROUP BY user_id, event_date) t1

                JOIN

               (select reciever_id,
                count(user_id) AS messages_received, 
                count(distinct(user_id)) AS users_received,
                toDate(time) as event_date
                from {db}.message_actions
                WHERE toDate(time) = yesterday() 
                GROUP BY reciever_id, event_date) t2

                ON t1.user_id = t2.reciever_id) t1_2

                JOIN

               (SELECT distinct(user_id), if(gender=0, 'male', 'female') as gender, age, os
                from {db}.message_actions) t3

                USING(user_id)

                '''
        df_cube2 = ph.read_clickhouse(query, connection = connection_from)
        return df_cube2
    
    
    @task
    def transform_merging(df1, df2):
        df = df1.merge(df2, how='outer', on=['user_id','event_date', 'gender', 'os', 'age']).fillna(0)
        return df
    
    
    @task
    def transform_gender(df_cube):
        df_cube_gender = df_cube[['event_date', 'gender', 'likes', 'views', 'messages_received', 'messages_sent', 'users_sent',                 'users_received']]\
            .groupby(['event_date', 'gender'])\
            .sum()\
            .reset_index()
        df_cube_gender = df_cube_gender.melt(id_vars=['event_date',  'likes', 'views', 'messages_received', 'messages_sent',                   'users_sent', 'users_received'],
                                var_name='dimension', value_name='dimension_value')
        return df_cube_gender

    
    @task
    def transform_os(df_cube):
        df_cube_os = df_cube[['event_date', 'os', 'likes', 'views', 'messages_received', 'messages_sent', 'users_sent',                         'users_received']]\
            .groupby(['event_date', 'os'])\
            .sum()\
            .reset_index()
        df_cube_os = df_cube_os.melt(id_vars=['event_date',  'likes', 'views', 'messages_received', 'messages_sent', 'users_sent',             'users_received'],
                                var_name='dimension', value_name='dimension_value')
        return df_cube_os
    
    @task
    def transform_age(df_cube):
        df_cube_age = df_cube[['event_date', 'age', 'likes', 'views', 'messages_received', 'messages_sent', 'users_sent',                       'users_received']]\
            .groupby(['event_date', 'age'])\
            .sum()\
            .reset_index()
        df_cube_age = df_cube_age.melt(id_vars=['event_date',  'likes', 'views', 'messages_received', 'messages_sent', 'users_sent',           'users_received'],
                                var_name='dimension', value_name='dimension_value')
        return df_cube_age
    
    
    @task
    def transform_concat_dfs(df_cube_os, df_cube_gender, df_cube_age):
        concat_dfs = pd.concat([df_cube_os, df_cube_gender, df_cube_age], axis=0)
        concat_dfs = concat_dfs[['event_date', 'dimension', 'dimension_value', 'likes', 'views', 'messages_received', 'messages_sent',               'users_sent', 'users_received']]
        concat_dfs = concat_dfs.astype({'views':'int64',
                        'likes':'int64',
                        'messages_received':'int64',
                        'messages_sent':'int64',
                        'users_received':'int64',
                        'users_sent':'int64'})

        return concat_dfs
    

    @task
    def load(df_all):
        query = '''CREATE TABLE IF NOT EXISTS test.a_ananchenko_20_etl
            (event_date Date,
            dimension String,
            dimension_value String,
            views Int64,
            likes Int64,
            messages_sent Int64,
            users_sent Int64,
            messages_received Int64,
            users_received Int64
            )
            ENGINE = MergeTree()
            ORDER BY event_date
            '''
        ph.execute(query = query, connection = connection_to)
        ph.to_clickhouse(df=df_all, table='a_ananchenko_20_etl', index=False, connection=connection_to)


   
    df_cube1 = extract1()
    df_cube2 = extract2()
    
    df_cube = transform_merging(df_cube1, df_cube2)
    
    df_cube_gender = transform_gender(df_cube)
    df_cube_os = transform_os(df_cube)
    df_cube_age = transform_age(df_cube)
    
    df_all = transform_concat_dfs(df_cube_os, df_cube_gender, df_cube_age)
    
    load(df_all)

    
dag_ananchenko = dag_ananchenko()
