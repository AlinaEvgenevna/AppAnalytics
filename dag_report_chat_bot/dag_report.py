import telegram
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import io
import pandas as pd
import pandahouse as ph
from datetime import date, datetime, timedelta
from io import StringIO
import requests
from airflow.decorators import dag, task
from airflow.operators.python import get_current_context



# Дефолтные параметры дага
default_args = {
    'owner': 'a-ananchenko-20',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2023, 7, 13),
}

# Интервал запуска DAG
schedule_interval = '0 11 * * *'

connection = {'host': '***',
                      '***',
                      '***, 
                      '***'
                     }

#dag

@dag(default_args=default_args, schedule_interval=schedule_interval, catchup=False)
def dag_report():
    

    @task()
    def extract():
        
        query = '''
        SELECT toDate(time) as day, 
              uniq(post_id) as posts,
              countIf(action='view') as views, 
              countIf(action='like') as likes,
              round(countIf(action='like') / countIf(action='view'), 4) as ctr,
              uniq(user_id) as dau
        FROM {db}.feed_actions
        WHERE toDate(time) BETWEEN (DATE(NOW()) - INTERVAL 8 DAY) AND (DATE(NOW()) - INTERVAL 1 DAY)
        GROUP BY day
       
        '''
        df = ph.read_clickhouse(query, connection = connection)
        df['day'] = pd.to_datetime(df['day'])
        df = df.astype({'views': int, 'likes': int, 'dau': int, 'posts': int})
        
        return df
    
    
    @task
    def get_message(df):
        day = pd.to_datetime(date.today() - timedelta(days = 1))
        day_before = pd.to_datetime(date.today() - timedelta(days = 2))
        week_before = pd.to_datetime(date.today() - timedelta(days = 8))

        dau = df[df.day == day]['dau'].iloc[0]
        dau_db = df[df.day == day_before]['dau'].iloc[0]
        dau_wb = df[df.day == week_before]['dau'].iloc[0]
        to_dau_db = (dau -  dau_db) /  dau_db
        to_dau_wb = (dau - dau_wb) / dau_wb

        likes = df[df.day == day]['likes'].iloc[0]
        likes_db = df[df.day == day_before]['likes'].iloc[0]
        likes_wb = df[df.day == week_before]['likes'].iloc[0]
        to_likes_db = (likes - likes_db) / likes_db
        to_likes_wb = (likes - likes_wb) / likes_wb

        views = df[df.day == day]['views'].iloc[0]
        views_db = df[df.day == day_before]['views'].iloc[0]
        views_wb = df[df.day == week_before]['views'].iloc[0]
        to_views_db = (views - views_db) / views_db
        to_views_wb = (views - views_wb) / views_wb

        ctr = df[df.day == day]['ctr'].iloc[0]
        ctr_db = df[df.day == day_before]['ctr'].iloc[0]
        ctr_wb = df[df.day == week_before]['ctr'].iloc[0]
        to_ctr_db = (ctr - ctr_db ) 
        to_ctr_wb = (ctr - ctr_wb) 

        lpu = df[df.day == day]['likes'].iloc[0] / df[df.day == day]['dau'].iloc[0]
        lpu_db = df[df.day == day_before]['likes'].iloc[0] / df[df.day == day_before]['dau'].iloc[0]
        lpu_wb = df[df.day == week_before]['likes'].iloc[0] / df[df.day == week_before]['dau'].iloc[0]
        to_lpu_db = (lpu - lpu_db) / lpu_db
        to_lpu_wb = (lpu - lpu_wb) / lpu_wb

        lpp = df[df.day == day]['likes'].iloc[0] / df[df.day == day]['posts'].iloc[0]
        lpp_db = df[df.day == day_before]['likes'].iloc[0] / df[df.day == day_before]['posts'].iloc[0]
        lpp_wb = df[df.day == week_before]['likes'].iloc[0] / df[df.day == week_before]['posts'].iloc[0]
        to_lpp_db = (lpp - lpp_db) / lpp_db
        to_lpp_wb = (lpp - lpp_wb) / lpp_wb

        a = f'ОТЧЕТ за {day.date()}'

        b = f'👫DAU: {dau} ({to_dau_db:+.2%} ко дню назад, {to_dau_wb:+.2%} к неделе назад)'

        c = f'👀Views: {views} ({to_views_db:+.2%} ко дню назад, {to_views_wb:+.2%} к неделе назад)'

        d = f'❤Likes: {likes} ({to_likes_db:+.2%} ко дню назад, {to_likes_wb:+.2%} к неделе назад)'

        e = f'🎯CTR: {ctr:.2} ({to_ctr_db:+.2%} ко дню назад, {to_ctr_wb:+.2%} к неделе назад)'

        f = f'👤Likes per user: {lpu:.2f} ({to_lpu_db:+.2%} ко дню назад, {to_lpu_wb:+.2%} к неделе назад)'

        g = f'🖼Likes per post: {lpp:.2f} ({to_lpp_db:+.2%} ко дню назад, {to_lpp_wb:+.2%} к неделе назад)'

        message = '\n'.join([a, '\n', b, c, d, e, f, g])

        return message
  


    @task
    def plot_report(df):
    
        yesterday = date.today() - timedelta(days = 1)
        start = (date.today() - timedelta(days = 7)).strftime("%d/%m/%Y")
        yesterday_f = yesterday.strftime("%d/%m/%Y")
        dates = [i.strftime("%d/%m/%Y") for i in pd.to_datetime(df['day'])]

        fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(10,10))
        sns.lineplot(x=dates, y=df['likes'], ax=ax2)
        sns.lineplot(x=dates, y=df['views'], ax=ax1)
        sns.lineplot(x=dates, y=df['ctr']*100, ax=ax3)
        sns.lineplot(x=dates, y=df['dau'], ax=ax4)

        ax1.set(xlabel=None)
        ax2.set(xlabel=None)
        ax3.set(xlabel=None)

        ax1.set_ylabel('Views')
        ax2.set_ylabel('Likes')
        ax3.set_ylabel('CTR (%)')
        ax4.set_ylabel('DAU')

        ax4.set_xlabel('Дата')

        fig.suptitle(f"Оновные метрики за {start} - {yesterday_f}")
        fig.tight_layout()

        plot_object = io.BytesIO()
        plt.savefig(plot_object)
        plot_object.seek(0)
        plot_object.name = 'plot.png'
        plt.close()

        return plot_object

    @task
    def send_report(message, plot_object):
    
        my_token = '***' 
        bot = telegram.Bot(token=my_token) 
        chat_id = ***

        bot.sendMessage(chat_id=chat_id, text=message)
        bot.sendPhoto(chat_id=chat_id, photo=plot_object)
    
    
    message = get_message(df)
    plot_object = plot_report(df)
    send_report(message, plot_object)
    
dag_report = dag_report()
