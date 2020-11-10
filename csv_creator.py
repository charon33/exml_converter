import csv
from typing import List
from loguru import logger
import os
import datetime


def write_to_csv(way_to_xml_dir, xml_file_name, actual_date, payers_dict, encoding="windows-1251"):
    logger.add(os.path.join(way_to_xml_dir,
                            "log",
                            "{0}_converter.log".format(
                                datetime.datetime.now().strftime('%Y_%m_%d')
                            )),
               format="{time} {level} {message}",
               level="INFO",
               rotation="10 Mb",
               compression="zip")
    list_of_dicts_with_payers: List = list()
    write_status = False
    csv_file_name = '{0}.csv'.format(xml_file_name.split('.')[0])
    way_to_csv_file = os.path.join(way_to_xml_dir, csv_file_name)
    exist_file_status = os.path.isfile(way_to_csv_file)
    list_of_fields: List[str] = ["Имя файла реестра",
                                 'Дата актуальности данных',
                                 'Лицевой счет',
                                 'ФИО',
                                 'Адрес',
                                 'Период',
                                 'Сумма',
                                 ]
    with open(way_to_csv_file, 'a', encoding=encoding) as csvfile:

        csv.register_dialect('pipes', delimiter=';')
        writer = csv.DictWriter(csvfile, fieldnames=list_of_fields, delimiter=';')

        if exist_file_status is False:
            writer.writeheader()

        for account_period_value in payers_dict:
            list_of_dicts_with_payers.append({"Имя файла реестра": xml_file_name,
                                              'Дата актуальности данных': actual_date,
                                              'Лицевой счет': account_period_value[0],
                                              'ФИО': payers_dict[account_period_value]["full_name"],
                                              'Адрес': payers_dict[account_period_value]["address"],
                                              'Период': account_period_value[1],
                                              'Сумма': payers_dict[account_period_value]["summ"],
                                              },
                                             )
        if list_of_dicts_with_payers:
            writer.writerows(list_of_dicts_with_payers)
            write_status = True
            logger.info("Файл {0} успешно конвертирован.".format(xml_file_name))
        else:
            logger.warning("Оказалось нечего записывать после парсинга файла {0}".format(xml_file_name))

        return write_status
