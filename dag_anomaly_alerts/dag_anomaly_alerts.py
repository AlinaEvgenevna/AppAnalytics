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


connection = {'host': '***',
                      '***',
                      'user':'***', 
                      'password':'***'
                     }


# Дефолтные параметры дага
default_args = {
    'owner': 'a-ananchenko-20',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2023, 7, 13),
}

# Интервал запуска DAG
schedule_interval = '*/15 * * * *'


# Основная фуннкция

def detect_anomaly(df, metric, a=2.5, n=7):
    
    df['q25'] = df[metric].shift(1).rolling(n).quantile(0.25)
    df['q75'] = df[metric].shift(1).rolling(n).quantile(0.75)
    df['iqr'] = df['q75'] - df['q25']
    df['low'] = df['q25'] - a * df['iqr']
    df['up'] = df['q75'] + a * df['iqr']
    
    df['low'] = df['low'].rolling(n, center=True, min_periods=1).mean()
    df['up'] = df['up'].rolling(n, center=True, min_periods=1).mean()

    df['is_out'] = np.where((df[metric] < df['low']) | (df[metric] > df['up']), True, False)
    df['diff'] = abs((df[metric] - df[metric].shift(1)) * 100 / df[metric].shift(1))
    
    # дополнительное условие для флага - разница с предыдущим >=  30%
    df['is_alert'] = np.where((df['is_out']) & (df['diff'] > 25), True, False )
    
    is_alert_last = df['is_alert'].iloc[-1]
    
    return df, is_alert_last
    



# dag

@dag(default_args=default_args, schedule_interval=schedule_interval, catchup=False)
def dag_anomaly_ananchenko():
    
    @task
    def extract_feed():
        
        query = '''
        SELECT toStartOfFifteenMinutes(time) as t15,
            toDate(time) as day,
            formatDateTime(t15, '%R') as hm,
            count(distinct(user_id)) as users,
            countIf(action='view') as views,
            countIf(action='like') as likes
            
            
            FROM {db}.feed_actions
            WHERE time > (today() - 1) AND time < toStartOfFifteenMinutes(now())      
            GROUP BY t15, day, hm
            ORDER BY t15
        
        '''

        df_feed = ph.read_clickhouse(query, connection = connection)
        
        return df_feed

    
    @task
    def extract_message():

        query = '''
        SELECT toStartOfFifteenMinutes(time) as t15,
            toDate(time) as day,
            formatDateTime(t15, '%R') as hm,
            count(distinct(user_id)) as users,
            count(reciever_id) as messages_sent

            FROM {db}.message_actions
            WHERE time > (today() - 1) AND time < toStartOfFifteenMinutes(now())      
            GROUP BY t15, day, hm
            ORDER BY t15

            '''

        df_message = ph.read_clickhouse(query, connection = connection)
        return df_message
        
        
    
        
    @task
    def send_alerts_feed(df):
    
        my_token = '***' 
        bot = telegram.Bot(token=my_token) 
        chat_id = ***
    
        for metric in ['users', 'views', 'likes']:
            df_anomaly, is_alert_last = detect_anomaly(df, metric)
        
            if is_alert_last == True:
                current_value = int(df[metric].iloc[-1])
                previous = int(df[metric].iloc[-2])
                diff = ((current_value - previous) / previous) * 100
                time = df['t15'].iloc[-1]

                link = "http://superset.lab.karpov.courses/r/4078"
                ps = 'Аномалиями в данном случае считаются значения, выходящие за границы интервала нормы и отклоняющиеся от предыдущего более, чем на 25%'
                
                message = '\n'.join(["Обнаружена аномалия в ленте новостей", '\n', f'Метрика: {metric}', f'Время: {time}', f'Текущее значение: {current_value}',f'Отклонение от предыдущего: {diff: .2f}%', 'Подробнее:', link, '\n', ps])

                bot.sendMessage(chat_id=chat_id, text=message)

                fig, ax = plt.subplots(1, 1, figsize=(16,8))
                sns.lineplot(data=df_anomaly, x= 't15', y= metric, color='blue',label=f'{metric}')
                sns.lineplot(data=df_anomaly, x= 't15', y= 'low', color='grey', alpha=0.25, label='Границы нормы')
                sns.lineplot(data=df_anomaly, x= 't15', y= 'up', color='grey', alpha=0.25)
                ax.fill_between(x= df_anomaly['t15'], y1=df_anomaly['low'], y2=df_anomaly['up'], color='grey', alpha=0.25)
                ax.set_title(f'Лента новостей: {metric}')
                ax.set_xlabel('Время')
                ax.set_ylabel(f'{metric}')
                sns.scatterplot(x= df_anomaly[df_anomaly['is_alert']]['t15'], y= df_anomaly[df_anomaly['is_alert']][metric], color='red', label='Аномалии')
                plt.scatter(x= df_anomaly['t15'].iloc[-1], y= df_anomaly[metric].iloc[-1], color='red', marker = 'o', label='Последняя аномалия')
                ax.set_xticks([min(df_anomaly['t15']), df_anomaly['t15'].iloc[len(df_anomaly['t15'])// 2], max(df_anomaly['t15'])])
                plt.legend()

                plot_object = io.BytesIO()
                fig.savefig(plot_object)
                plot_object.seek(0)
                plot_object.name = f'{metric}.png'
                plt.close()

                bot.sendPhoto(chat_id=chat_id, photo=plot_object)

    
    
    @task
    def send_alerts_message(df):
    
        my_token = '***' 
        bot = telegram.Bot(token=my_token) 
        chat_id = ***
    
        for metric in ['users', 'messages_sent']:
            df_anomaly, is_alert_last = detect_anomaly(df, metric)
        
            if is_alert_last == True:
                current_value = int(df[metric].iloc[-1])
                previous = int(df[metric].iloc[-2])
                diff = ((current_value - previous) / previous) * 100
                time = df['t15'].iloc[-1]

                link = "http://superset.lab.karpov.courses/r/4079"
                ps = 'Аномалиями в данном случае считаются значения, выходящие за границы интервала нормы и отклоняющиеся от предыдущего более, чем на 25%'
                message = '\n'.join(["Обнаружена аномалия в мессенджере", '\n', f'Метрика: {metric}', f'Время: {time}', f'Текущее значение: {current_value}',f'Отклонение от предыдущего: {diff: .2f}%', 'Подробнее:', link,'\n', ps])

                bot.sendMessage(chat_id=chat_id, text=message)

                fig, ax = plt.subplots(1, 1, figsize=(16,8))
                sns.lineplot(data=df_anomaly, x= 't15', y= metric, color='blue',label=f'{metric}')
                sns.lineplot(data=df_anomaly, x= 't15', y= 'low', color='grey', alpha=0.25, label='Границы нормы')
                sns.lineplot(data=df_anomaly, x= 't15', y= 'up', color='grey', alpha=0.25)
                ax.fill_between(x= df_anomaly['t15'], y1=df_anomaly['low'], y2=df_anomaly['up'], color='grey', alpha=0.25)
                ax.set_title(f'Мессенджер: {metric}')
                ax.set_xlabel('Время')
                ax.set_ylabel(f'{metric}')
                sns.scatterplot(x= df_anomaly[df_anomaly['is_alert']]['t15'], y= df_anomaly[df_anomaly['is_alert']][metric], color='red', label='Аномалии')
                plt.scatter(x= df_anomaly['t15'].iloc[-1], y= df_anomaly[metric].iloc[-1], color='red', marker = 'o', label='Последняя аномалия')
                ax.set_xticks([min(df_anomaly['t15']), df_anomaly['t15'].iloc[len(df_anomaly['t15'])// 2], max(df_anomaly['t15'])])
                plt.legend()



                plot_object = io.BytesIO()
                fig.savefig(plot_object)
                plot_object.seek(0)
                plot_object.name = f'{metric}.png'
                plt.close()

                bot.sendPhoto(chat_id=chat_id, photo=plot_object)

    
    
    df_feed = extract_feed()
    send_alerts_feed(df_feed)  
    
    df_message = extract_message()
    send_alerts_message(df_message)
    
dag_anomaly_ananchenko = dag_anomaly_ananchenko()
