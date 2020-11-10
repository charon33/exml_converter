from xml.etree import ElementTree as ET
from csv_creator import write_to_csv
from xml.etree.ElementTree import Element
from typing import List, Dict, Optional, Tuple, NoReturn
import datetime
from loguru import logger
import re
import sys
import os



ROUND_VAR = 2
FLOAT_EXCEPTIONS_LIST = ["NaN", "-iNF", "infinity", ]


def find_encoding_in_string(line: Optional[str]) -> Optional[str]:
    """Ищем кодировку в строке и возвращаем ее или None"""
    encode_result: Optional = None
    patterm = re.compile(r"""encoding=\s*['"](.+)['"]\s*""")
    encode_string = patterm.findall(line)
    if encode_string:
        encode_result = encode_string[0]
    return encode_result if encode_result else None


def get_childes(element: Element) -> List:
    """Получение дочерних элементов, необходимо из за
    отключения функции getchildren"""

    childes_list = list()
    for children in list(element):
        childes_list.append(children)
    return childes_list


def get_payers_from_xml(tree: ET.ElementTree,
                        list_with_lines_of_payers: List[int]) -> Dict:
    """Поиск и добавление в словарь Плательщиков с номерами строк"""
    payers_dict: Dict[int, Element] = dict()
    count = 0
    for elem in tree.iter():
        if elem.tag == 'Плательщик':
            payers_dict[list_with_lines_of_payers[count] + 1] = elem
            count = count + 1
    return payers_dict


def get_numbers_of_pyments_in_lines(xml_file: str) -> Tuple[Optional[List[int]],Optional[str]]:
    """Получаем номера строк, где встречается Плательщик и возвращаем line_list или None"""
    line_list: List[int] = list()
    xml_encoding:Optional(str) = None
    with open(xml_file, 'r', encoding='windows-1251') as file:
        for num, line in enumerate(file):
            encoding = find_encoding_in_string(line)
            if encoding:
                xml_encoding = encoding
            if "<Плательщик>" in line:
                line_list.append(num)
        logger.info("Кодировка документа {0}".format(xml_encoding))
    if line_list:
        return line_list, xml_encoding
    else:
        return None, xml_encoding


def get_payers_properties(payers_dict: Dict[int, Element]) \
        -> Optional[Dict[Tuple, Dict]]:
    """Получаем свойства плательщика из payers_dict,
     лицевой, фио, адресс, сумму, период, добавляем тэг for_delete
     для удаления дубля, заменяем ключ и возвращаем словарь или ничего"""
    validate_summ_status: bool = True
    result_dict: Dict[Tuple, Dict] = dict()
    for num in payers_dict:
        payer = payers_dict[num]
        account = payer.find("ЛицСч").text
        period = _validate_period_string(payer.find("Период").text, "%m%Y")
        address = payer.find("Адрес").text
        summ = payer.find("Сумма").text
        full_name = payer.find("ФИО").text
        if summ:
            validate_summ_status, summ = _validate_summ_string(summ, ROUND_VAR)
        if not validate_summ_status:
            logger.warning("Некорректная запись суммы в строках плательщика {0}".format(
                num
            ))
        if account is not None and period is not None and validate_summ_status:
            if (account, period,) not in result_dict.keys():
                result_dict[(account, period,)] = {"full_name": full_name,
                                                   "address": address,
                                                   "summ": summ,
                                                   'string_in_file': num,
                                                   "for_delete": False,
                                                   }
            else:
                logger.warning("Повторяющееся значение Лицевой + Период \
в строках плательщика {0}".format(num)
                               )
                result_dict[(account, period,)]['for_delete'] = True
        else:
            logger.warning("Отсутствие одного из ключевых элементов \
в строках плательщика {0}".format(num))
    if result_dict:
        return result_dict
    else:
        return None


def _validate_period_string(string: str, pattern: str) -> Optional[datetime.date]:
    """Проверяем дату на соответствие заданным требованиям"""

    try:
        converted_date = datetime.datetime.strptime(string, pattern).date()
    except ValueError:
        if pattern == '%d.%m.%Y':
            logger.critical('Не верный формат актуальной даты')
        return None
    except Exception as e:
        if string:
            logger.critical(e)
        return None
    else:
        return converted_date


def _validate_summ_string(summ_string: str, round_var) -> Tuple[bool, Optional[float]]:
    """Заменяем запятые если есть на точки: проверяем, является ли значение float
    и соответствует ли заданным треббованиям"""
    validation_status: bool = False
    summ_string = summ_string.replace(',', '.')

    # Проверяем вхождение исключений для типа float в нашу строку
    for float_exception in FLOAT_EXCEPTIONS_LIST:
        if float_exception not in summ_string:
            try:
                converted_summ = round(float(summ_string), round_var)
            except Exception:
                return validation_status, None
            else:
                validation_status = True
                return validation_status, converted_summ
        else:
            return validation_status, None


def _remove_duplicates_in_payers(payers_properties_dict: \
        Dict[Tuple[str, datetime.date], Dict]) -> Optional[Dict[Tuple, Dict]]:
    """Убирает оставшиеся строки при совпадении значений лицевой + период
    если они уже есть в словаре"""
    lines_for_delete: List[Tuple] = list()
    if payers_properties_dict and type(payers_properties_dict) is dict:
        for account_period_tuple in payers_properties_dict:
            if payers_properties_dict[account_period_tuple]['for_delete']:
                logger.warning("Повторяющееся значение Лицевой + Период \
в строках плательщика {0}".format(
                    payers_properties_dict[account_period_tuple]['string_in_file']
                ))
                lines_for_delete.append(account_period_tuple)
        if lines_for_delete:
            for line in lines_for_delete:
                del payers_properties_dict[line]
        return payers_properties_dict
    else:
        return None


def get_file_actual_date(tree: ET.ElementTree)-> Optional[datetime.date]:
    """Получаем дату актуальности файла"""

    for element in tree.iter():
        if element.tag == "ДатаФайл":
            actual_date = _validate_period_string(element.text, '%d.%m.%Y')
            logger.info("Актуальная дата файла {0}".format(actual_date))
            return actual_date
    return None


def create_dirs_for_files(way_to_xml:str) -> str:
    """Проверяем наличие и создаем папки"""
    way_to_xml_dir = way_to_xml[:-len(os.path.basename(way_to_xml))]
    if not os.path.exists(os.path.join(way_to_xml_dir, 'arh')):
        os.mkdir(os.path.join(way_to_xml_dir, 'arh'))

    if not os.path.exists(os.path.join(way_to_xml_dir, 'bad')):
        os.mkdir(os.path.join(way_to_xml_dir, 'bad'))

    if not os.path.exists(os.path.join(way_to_xml_dir, 'log')):
        os.mkdir(os.path.join(way_to_xml_dir, 'log'))
    return way_to_xml_dir


def move_xml(way_to_xml:str, way_to_xml_dir:str, end_dir: str) -> NoReturn:
    """Переносим файл, если он не xml в папку bad или arh если все хорошо"""
    if os.path.exists(way_to_xml) and os.path.exists(os.path.join(way_to_xml_dir, end_dir)):
        os.replace(way_to_xml, os.path.join(way_to_xml_dir,
                                            end_dir,
                                            os.path.basename(way_to_xml)
                                            )
                   )
    else:
        logger.error("Не могу перенести файл, т.к. не доступен он или его путь назначения.")

def parse_xml(xml_file: str) -> Tuple[Dict[Tuple, Dict], Optional[str]]:
    """
    Парсинг XML используя ElementTree
    """
    way_to_xml_dir = create_dirs_for_files(way_to_xml=xml_file)
    logger.add(os.path.join(way_to_xml_dir,
                            "log",
                            "{0}_converter.log".format(
                                datetime.datetime.now().strftime('%Y_%m_%d')
                            )),
               format="{time} {level} {message}",
               level="INFO",
               rotation="10 Mb",
               compression="zip")

    logger.info("Начинаем обработку файла {0}".format(os.path.basename(xml_file)))
    try:
        tree = ET.ElementTree(file=xml_file)
    except Exception as err:
        logger.critical('Ошибка при парсинге файла {0}'.format(xml_file))
        way_to_xml_dir = create_dirs_for_files(way_to_xml=xml_file)
        move_xml(way_to_xml=xml_file,
                 way_to_xml_dir=way_to_xml_dir,
                 end_dir='bad'
                 )
        sys.exit(-1)

    actual_date_of_file = get_file_actual_date(tree=tree)
    if not actual_date_of_file:
        logger.critical('Не смогли найти дату актуальности файла, либо она не корректна')
        sys.exit('-1')
    list_with_lines_of_payers, xml_encode = get_numbers_of_pyments_in_lines(
        xml_file=xml_file
    )
    payers = get_payers_from_xml(
        tree=tree,
        list_with_lines_of_payers= list_with_lines_of_payers
    )
    payers_properties_dict = get_payers_properties(payers_dict=payers)
    payers_properties_dict = _remove_duplicates_in_payers(
        payers_properties_dict
    )
    if payers_properties_dict:
        write_status = write_to_csv(way_to_xml_dir=way_to_xml_dir,
                                    xml_file_name=os.path.basename(xml_file),
                                    actual_date=actual_date_of_file,
                                    payers_dict=payers_properties_dict,
                                    encoding=xml_encode
                                    )

    move_xml(way_to_xml=xml_file,
             way_to_xml_dir=way_to_xml_dir,
             end_dir='arh'
             )

    return payers_properties_dict, xml_encode
