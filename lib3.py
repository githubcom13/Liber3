import re
import time
import requests
import datetime
from typing import List
from decimal import Decimal


def prepare_sql(sql_tpl: str, args: (list, tuple)):
    return sql_tpl % escape_args(args)


def escape_args(args):
    if isinstance(args, (tuple, list)):
        return tuple(literal(arg) for arg in args)
    elif isinstance(args, dict):
        return {key: literal(val) for (key, val) in args.items()}
    else:
        # If it's not a dictionary let's try escaping it anyways.
        # Worst case it will throw a Value error
        return escape(args)


def literal(obj):
    """Alias for escape()

    Non-standard, for internal use; do not use this in your applications.
    """
    return escape(obj, encoders)


def escape(obj, mapping=None):
    """Escape whatever value you pass to it.

    Non-standard, for internal use; do not use this in your applications.
    """
    if isinstance(obj, str):
        return "'" + escape_string(obj) + "'"
    if isinstance(obj, (bytes, bytearray)):
        ret = escape_bytes(obj)
        return ret
    return escape_item(obj, "utf8mb4", mapping=mapping)


def escape_item(val, charset, mapping=None):
    if mapping is None:
        mapping = encoders
    encoder = mapping.get(type(val))

    # Fallback to default when no encoder found
    if not encoder:
        try:
            encoder = mapping[str]
        except KeyError:
            raise TypeError("no default type converter defined")

    if encoder in (escape_dict, escape_sequence):
        val = encoder(val, charset, mapping)
    else:
        val = encoder(val, mapping)
    return val


def escape_dict(val, charset, mapping=None):
    n = {}
    for k, v in val.items():
        quoted = escape_item(v, charset, mapping)
        n[k] = quoted
    return n


def escape_sequence(val, charset, mapping=None):
    n = []
    for item in val:
        quoted = escape_item(item, charset, mapping)
        n.append(quoted)
    return "(" + ",".join(n) + ")"


def escape_set(val, charset, mapping=None):
    return ",".join([escape_item(x, charset, mapping) for x in val])


def escape_bool(value, mapping=None):
    return str(int(value))


def escape_int(value, mapping=None):
    return str(value)


def escape_float(value, mapping=None):
    s = repr(value)
    if s in ("inf", "nan"):
        return s
    if "e" not in s:
        s += "e0"
    return s


_escape_table = [chr(x) for x in range(128)]
_escape_table[0] = "\\0"
_escape_table[ord("\\")] = "\\\\"
_escape_table[ord("\n")] = "\\n"
_escape_table[ord("\r")] = "\\r"
_escape_table[ord("\032")] = "\\Z"
_escape_table[ord('"')] = '\\"'
_escape_table[ord("'")] = "\\'"


def escape_string(value, mapping=None):
    """escapes *value* without adding quote.

    Value should be unicode
    """
    return value.translate(_escape_table)


def escape_bytes_prefixed(value, mapping=None):
    return "_binary'%s'" % value.decode("ascii", "surrogateescape").translate(
        _escape_table
    )


def escape_bytes(value, mapping=None):
    return "'%s'" % value.decode("ascii", "surrogateescape").translate(_escape_table)


def escape_str(value, mapping=None):
    return "'%s'" % escape_string(str(value), mapping)


def escape_None(value, mapping=None):
    return "NULL"


def escape_timedelta(obj, mapping=None):
    seconds = int(obj.seconds) % 60
    minutes = int(obj.seconds // 60) % 60
    hours = int(obj.seconds // 3600) % 24 + int(obj.days) * 24
    if obj.microseconds:
        fmt = "'{0:02d}:{1:02d}:{2:02d}.{3:06d}'"
    else:
        fmt = "'{0:02d}:{1:02d}:{2:02d}'"
    return fmt.format(hours, minutes, seconds, obj.microseconds)


def escape_time(obj, mapping=None):
    if obj.microsecond:
        fmt = "'{0.hour:02}:{0.minute:02}:{0.second:02}.{0.microsecond:06}'"
    else:
        fmt = "'{0.hour:02}:{0.minute:02}:{0.second:02}'"
    return fmt.format(obj)


def escape_datetime(obj, mapping=None):
    if obj.microsecond:
        fmt = "'{0.year:04}-{0.month:02}-{0.day:02} {0.hour:02}:{0.minute:02}:{0.second:02}.{0.microsecond:06}'"
    else:
        fmt = "'{0.year:04}-{0.month:02}-{0.day:02} {0.hour:02}:{0.minute:02}:{0.second:02}'"
    return fmt.format(obj)


def escape_date(obj, mapping=None):
    fmt = "'{0.year:04}-{0.month:02}-{0.day:02}'"
    return fmt.format(obj)


def escape_struct_time(obj, mapping=None):
    return escape_datetime(datetime.datetime(*obj[:6]))


def Decimal2Literal(o, d):
    return format(o, "f")


def _convert_second_fraction(s):
    if not s:
        return 0
    # Pad zeros to ensure the fraction length in microseconds
    s = s.ljust(6, "0")
    return int(s[:6])


DATETIME_RE = re.compile(
    r"(\d{1,4})-(\d{1,2})-(\d{1,2})[T ](\d{1,2}):(\d{1,2}):(\d{1,2})(?:.(\d{1,6}))?"
)


def convert_datetime(obj):
    """Returns a DATETIME or TIMESTAMP column value as a datetime object:

      >>> datetime_or_None('2007-02-25 23:06:20')
      datetime.datetime(2007, 2, 25, 23, 6, 20)
      >>> datetime_or_None('2007-02-25T23:06:20')
      datetime.datetime(2007, 2, 25, 23, 6, 20)

    Illegal values are returned as None:

      >>> datetime_or_None('2007-02-31T23:06:20') is None
      True
      >>> datetime_or_None('0000-00-00 00:00:00') is None
      True

    """
    if isinstance(obj, (bytes, bytearray)):
        obj = obj.decode("ascii")

    m = DATETIME_RE.match(obj)
    if not m:
        return convert_date(obj)

    try:
        groups = list(m.groups())
        groups[-1] = _convert_second_fraction(groups[-1])
        return datetime.datetime(*[int(x) for x in groups])
    except ValueError:
        return convert_date(obj)


TIMEDELTA_RE = re.compile(r"(-)?(\d{1,3}):(\d{1,2}):(\d{1,2})(?:.(\d{1,6}))?")


def convert_timedelta(obj):
    """Returns a TIME column as a timedelta object:

      >>> timedelta_or_None('25:06:17')
      datetime.timedelta(1, 3977)
      >>> timedelta_or_None('-25:06:17')
      datetime.timedelta(-2, 83177)

    Illegal values are returned as None:

      >>> timedelta_or_None('random crap') is None
      True

    Note that MySQL always returns TIME columns as (+|-)HH:MM:SS, but
    can accept values as (+|-)DD HH:MM:SS. The latter format will not
    be parsed correctly by this function.
    """
    if isinstance(obj, (bytes, bytearray)):
        obj = obj.decode("ascii")

    m = TIMEDELTA_RE.match(obj)
    if not m:
        return obj

    try:
        groups = list(m.groups())
        groups[-1] = _convert_second_fraction(groups[-1])
        negate = -1 if groups[0] else 1
        hours, minutes, seconds, microseconds = groups[1:]

        tdelta = (
                datetime.timedelta(
                    hours=int(hours),
                    minutes=int(minutes),
                    seconds=int(seconds),
                    microseconds=int(microseconds),
                )
                * negate
        )
        return tdelta
    except ValueError:
        return obj


TIME_RE = re.compile(r"(\d{1,2}):(\d{1,2}):(\d{1,2})(?:.(\d{1,6}))?")


def convert_time(obj):
    """Returns a TIME column as a time object:

      >>> time_or_None('15:06:17')
      datetime.time(15, 6, 17)

    Illegal values are returned as None:

      >>> time_or_None('-25:06:17') is None
      True
      >>> time_or_None('random crap') is None
      True

    Note that MySQL always returns TIME columns as (+|-)HH:MM:SS, but
    can accept values as (+|-)DD HH:MM:SS. The latter format will not
    be parsed correctly by this function.

    Also note that MySQL's TIME column corresponds more closely to
    Python's timedelta and not time. However if you want TIME columns
    to be treated as time-of-day and not a time offset, then you can
    use set this function as the converter for FIELD_TYPE.TIME.
    """
    if isinstance(obj, (bytes, bytearray)):
        obj = obj.decode("ascii")

    m = TIME_RE.match(obj)
    if not m:
        return obj

    try:
        groups = list(m.groups())
        groups[-1] = _convert_second_fraction(groups[-1])
        hours, minutes, seconds, microseconds = groups
        return datetime.time(
            hour=int(hours),
            minute=int(minutes),
            second=int(seconds),
            microsecond=int(microseconds),
        )
    except ValueError:
        return obj


def convert_date(obj):
    """Returns a DATE column as a date object:

      >>> date_or_None('2007-02-26')
      datetime.date(2007, 2, 26)

    Illegal values are returned as None:

      >>> date_or_None('2007-02-31') is None
      True
      >>> date_or_None('0000-00-00') is None
      True

    """
    if isinstance(obj, (bytes, bytearray)):
        obj = obj.decode("ascii")
    try:
        return datetime.date(*[int(x) for x in obj.split("-", 2)])
    except ValueError:
        return obj


def through(x):
    return x


convert_bit = through

encoders = {
    bool: escape_bool,
    int: escape_int,
    float: escape_float,
    str: escape_str,
    bytes: escape_bytes,
    tuple: escape_sequence,
    list: escape_sequence,
    set: escape_sequence,
    frozenset: escape_sequence,
    dict: escape_dict,
    type(None): escape_None,
    datetime.date: escape_date,
    datetime.datetime: escape_datetime,
    datetime.timedelta: escape_timedelta,
    datetime.time: escape_time,
    time.struct_time: escape_struct_time,
    Decimal: Decimal2Literal,
}
DECIMAL = 0
TINY = 1
SHORT = 2
LONG = 3
FLOAT = 4
DOUBLE = 5
NULL = 6
TIMESTAMP = 7
LONGLONG = 8
INT24 = 9
DATE = 10
TIME = 11
DATETIME = 12
YEAR = 13
NEWDATE = 14
VARCHAR = 15
BIT = 16
JSON = 245
NEWDECIMAL = 246
ENUM = 247
SET = 248
TINY_BLOB = 249
MEDIUM_BLOB = 250
LONG_BLOB = 251
BLOB = 252
VAR_STRING = 253
STRING = 254
GEOMETRY = 255

CHAR = TINY
INTERVAL = ENUM

decoders = {
    BIT: convert_bit,
    TINY: int,
    SHORT: int,
    LONG: int,
    FLOAT: float,
    DOUBLE: float,
    LONGLONG: int,
    INT24: int,
    YEAR: int,
    TIMESTAMP: convert_datetime,
    DATETIME: convert_datetime,
    TIME: convert_timedelta,
    DATE: convert_date,
    BLOB: through,
    TINY_BLOB: through,
    MEDIUM_BLOB: through,
    LONG_BLOB: through,
    STRING: through,
    VAR_STRING: through,
    VARCHAR: through,
    DECIMAL: Decimal,
    NEWDECIMAL: Decimal,
}

# for MySQLdb compatibility
conversions = encoders.copy()
conversions.update(decoders)
Thing2Literal = escape_str

encoders = {k: v for (k, v) in conversions.items() if type(k) is not int}


def format_file_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes // 1024} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes // (1024 * 1024)} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def get_icon(c):
    icons = {
        'video': ':movie_camera:',
        'document': ':green_book:',
        'music': ':musical_note:',
        'software': ':laptop_computer:',
        'image': ':art:'
    }
    return icons.get(c, ':rocket:')


def query_string_prepare(queries: list):
    query_string = []
    for query in queries:
        query_string.append(str(query))

    rst = " ".join(query_string)
    return rst


def highlight_prepare(fields: List[str]):
    place_hold = ",".join(["\"{}\""] * len(fields))
    option = """{"highlight":{ "style":"html","fields":[""" + place_hold.format(*fields) + """]}}"""
    option = option.translate({ord('"'): "\""})
    return "/*+ SET_VAR(full_text_option='%s')*/" % option


def get_sql(args):
    query = args.terms
    title = "{}:{}^{}".format("title", "\"" + query + "\"", 1.0)
    author = "{}:{}^{}".format("author", "\"" + query + "\"", 1.0)
    queries = [title, author]
    query_str = query_string_prepare(queries)
    highlight = highlight_prepare(["title", "author"])

    filter_type = get_filter_type(args.type)

    if filter_type == 'all':
        sql = prepare_sql(
            "select {} ipfs_cid,title,author,extension,language,publisher,year,filesize from library.ebook where "
            "query_string_recency(%s) ".format(highlight), [query_str])
    else:
        query_str = [query_str, filter_type]
        sql = prepare_sql(
            "select {} ipfs_cid,title,author,extension,language,publisher,year,filesize from  library.ebook where query_string_recency(%s) and extension=%s ".format(
                highlight), query_str)

    page = args.page * args.limit
    sql += "limit {},{}".format(page, args.limit)

    return sql


def get_filter_type(filter_type):
    ftypes = {
        'epub': 'epub',
        'pdf': 'pdf',
        'mobi': 'mobi',
        'azw3': 'azw3',
        'djvu': 'djvu',
    }

    return ftypes.get(filter_type, 'all')


def get_order_type(order_type):
    otypes = {
        'date': 'year'
    }
    return otypes.get(order_type, 'none')


def query(args):
    sql = get_sql(args)
    endpoint = "https://gateway.magnode.ru/blockved/glitterchain/index/sql/simple_query"
    req = {"sql": sql, "arguments": []}
    r = requests.post(endpoint, json=req, timeout=30)
    if r.status_code != 200:
        return
    rst = r.json()
    return rst


def main():
    import time
    import argparse
    from rich.console import Console
    from rich.table import Table
    from rich.align import Align
    from rich.tree import Tree
    from rich.text import Text

    parser = argparse.ArgumentParser()
    parser.add_argument('terms', type=str,
                        help='the desired terms for searching.')
    parser.add_argument('-p', '--page', type=int, default=0,
                        help='The page of results you would like to display.')
    parser.add_argument('-l', '--limit', type=int, default=10,
                        help='The limit of per page you would like to display.')
    parser.add_argument('-t', '--type', type=str, default='all',
                        help='The type of results you would like to display.')

    args = parser.parse_args()

    rst = query(args)

    console = Console()
    table = Table(show_header=True, header_style="bold magenta", expand=True)
    table_centered = Align.center(table)
    link = "You could also try a web version running on ENS & IPFS:\n https://liber3.eth.limo/"
    table.add_column(link)
    table.add_column("ext", style="dim", no_wrap=True)

    for row in rst['result']:
        row = row['row']
        ext = Tree(row["extension"]["value"])
        ext.add(row["year"]["value"])
        ext.add(format_file_size(float(row["filesize"]["value"])))
        ext.add(row["language"]["value"])

        ipfs = "https://cloudflare-ipfs.com/ipfs/{}".format(row["ipfs_cid"]["value"])
        content = Tree(Text(ipfs, overflow="fold"))
        title = row["_highlight_title"]["value"].replace("<mark>", "[red]").replace("</mark>", "[/red]")
        author = row["_highlight_author"]["value"].replace("<mark>", "[red]").replace("</mark>", "[/red]")
        content.add(title)
        content.add(author)

        table.add_row(content, ext)

    console.print(table)


if __name__ == '__main__':
    main()
