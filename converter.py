# -*- coding: UTF-8 -*-

from xml_part import parse_xml
import sys
import argparse


def createParser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--path')

    return parser


if __name__ == '__main__':
    parser = createParser()
    namespace = parser.parse_args(sys.argv[1:])
    parse_xml(namespace.path)


