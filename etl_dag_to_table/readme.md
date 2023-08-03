# Настройка ETL-pipeline

Автоматизация создания отчетной таблицы по каждому дню.

### Задача

Построить Dag Airflow, который будет запускаться каждый день и присылать данные по предыдущему дню в виде таблицы в ClickHouse.


### Структура итоговой таблицы

* Пользователи разбиты на срезы по полу, возрасту и операционной системе. 

* Для каждого среза - указаны основные метрики (просмотры, лайки, отправленные cобщения, полученные сообщения).

## Файлы

1. [Файл с кодом](https://github.com/AlinaEvgenevna/AppAnalytics/blob/main/etl_dag_to_table/etl_dag_to_table.py)
   NB Это копия рабочего файла .py, данные для connection скрыты.
   
3. [Скрин dag tree](https://github.com/AlinaEvgenevna/AppAnalytics/blob/main/etl_dag_to_table/dag_tree.png)
4. [Скрин dag graph](https://github.com/AlinaEvgenevna/AppAnalytics/blob/main/etl_dag_to_table/dag_graph.png)




### Инструменты

Python, git, Airflow, ClickHouse

