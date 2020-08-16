import lxml.etree as etree
import requests
import os
import py_compile
import uuid
import importlib.util
import json
import sys

from common.settings import PARSERS_DIR


def compile_parser_code(parser_module_path, parser_filename):
    try:
        py_compile.compile(parser_module_path, dfile=parser_filename, doraise=True)
    except py_compile.PyCompileError as ex:
        return False, str(ex)

    return True, None


def check_required_function(parser_module):
    has_func = False
    err = None
    try:
        has_func = callable(parser_module.parse_page)
    except Exception as ex:
        err = str(ex)
    return has_func, err


def import_parser_module(parser_name, parser_abspath):
    spec = importlib.util.spec_from_file_location(parser_name, parser_abspath)
    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    return parser


def get_page_dom(url):
    try:
        page = requests.get(url, verify=False)
        dom = etree.HTML(page.text)
    except Exception as ex:
        err_msg = "Couldn't make dom for page url '%s': %s" % (url, str(ex))
        return None, err_msg

    return dom, None


def run_parser(dom, module, parameter):
    parse_ok = True
    parameter_json = None
    if parameter:
        try:
            parameter = parameter.strip('"')
            parameter_json = json.loads(parameter)
        except Exception as ex:
            parse_ok = False
            parse_result = "Failed converting parser parameter to json: %s" % str(ex)
    if parse_ok:
        try:
            parse_result = module.parse_page(dom, parameter_json)
        except Exception as ex:
            parse_result = "Parser raised an exception:\n%s" % str(ex)
            parse_ok = False

    return parse_ok, parse_result


def make_parser_module(parser_code, parser_name, parsers_dir):
    base_name = str(uuid.uuid4())
    parser_filename = base_name + ".py"
    parser_abspath = os.path.join(parsers_dir, parser_filename)
    parser_module = None
    error_message = None

    try:
        with open(parser_abspath, 'w') as parser_file:
            parser_file.write(parser_code)
    except Exception as ex:
        error_message = "Couldn't create parser file: %s" % str(ex)

    if not error_message:
        try:
            compres, compmsg = compile_parser_code(parser_abspath, parser_filename)
            if compres:
                parser_module = import_parser_module(parser_name, parser_abspath)
            else:
                error_message = compmsg
        except Exception as ex:
            error_message = "Couldn't import module for parser '%s'. Error while module loading: %s" % (parser_name, str(ex))
            parser_module = None
        try:
            os.remove(parser_abspath)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
    pycache_path = os.path.join(parsers_dir, "__pycache__", base_name)
    bytecode_path = "%s.%s.pyc" % (pycache_path, sys.implementation.cache_tag)
    return parser_module, error_message, parser_code, bytecode_path


class ParsingResult:
    NO_CODE = 0x1486
    NO_PARSER = 0x1487

    OK = 0x1488

    DOM_FAILED = 0x1489

    PARSER_FAILED = 0x1490

    MODULE_FAILED = 0x1491

    UNKNOWN = 0x9999


def do_parse(parser_db_obj, parser_parameter, page_dom):
    parser_exec_res = ParsingResult.UNKNOWN
    parser_module = None
    parser_code = None
    label_message = "Parser execution failed:"
    bytecode_path = None
    if not parser_db_obj:
        parser_result = "No parser found in database"
        parser_exec_res = ParsingResult.NO_PARSER
    elif parser_db_obj.code:
        parser_module, parser_result, parser_code, bytecode_path = make_parser_module(parser_db_obj.code, parser_db_obj.name, PARSERS_DIR)
    else:
        parser_exec_res = ParsingResult.NO_CODE
        parser_result = "No parser code supplied"

    if parser_module:
        parser_exec_ok, parser_result = run_parser(page_dom, parser_module, parser_parameter)

        if parser_exec_ok:
            try:
                parser_result = str(parser_result)
            except Exception as ex:
                parser_exec_res = ParsingResult.PARSER_FAILED
                parser_result = "Failed converting parser result to string: %s" % str(ex)

            if parser_exec_res != ParsingResult.PARSER_FAILED:
                parser_exec_res = ParsingResult.OK
                label_message = "Parser executed successfuly. Result: "
        else:
            parser_exec_res = ParsingResult.PARSER_FAILED
    elif parser_db_obj:
        parser_exec_res = ParsingResult.MODULE_FAILED
        label_message = "Couldn't load parser module for parser '%s'" % parser_db_obj.name

    if bytecode_path:
        try:
            os.remove(bytecode_path)
        except OSError as e:
            print("Failed removing parser cache file: '%s'. Error: %s" % (bytecode_path, e))

    return parser_exec_res, parser_result, label_message, parser_code
