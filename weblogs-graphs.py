import sys
import gzip

import pandas as pd
import numpy as np

METHODS = {
    0: "GET",
    1: "HEAD",
    2: "POST",
    3: "PUT",
    4: "DELETE",
    5: "TRACE",
    6: "OPTIONS",
    7: "CONNECT",
    8: "OTHER_METHODS",
}
TYPES = {
    0: "HTML",
    1: "IMAGE",
    2: "AUDIO",
    3: "VIDEO",
    4: "JAVA",
    5: "FORMATTED",
    6: "DYNAMIC",
    7: "TEXT",
    8: "COMPRESSED",
    9: "PROGRAMS",
    10: "DIRECTORY",
    11: "ICL",
    12: "OTHER_TYPES",
    13: "NUM_OF_FILETYPES",
}
STATUS = {
        0: "SC_100",
        1: "SC_101",
        2: "SC_200",
        3: "SC_201",
        4: "SC_202",
        5: "SC_203",
        6: "SC_204",
        7: "SC_205",
        8: "SC_206",
        9: "SC_300",
       10: "SC_301",
       11: "SC_302",
       12: "SC_303",
       13: "SC_304",
       14: "SC_305",
       15: "SC_400",
       16: "SC_401",
       17: "SC_402",
       18: "SC_403",
       19: "SC_404",
       20: "SC_405",
       21: "SC_406",
       22: "SC_407",
       23: "SC_408",
       24: "SC_409",
       25: "SC_410",
       26: "SC_411",
       27: "SC_412",
       28: "SC_413",
       29: "SC_414",
       30: "SC_415",
       31: "SC_500",
       32: "SC_501",
       33: "SC_502",
       34: "SC_503",
       35: "SC_504",
       36: "SC_505",
       37: "OTHER_CODES",
}

def request_type():
    """
struct request {
 uint32_t timestamp;
 uint32_t clientID;
 uint32_t objectID;
 uint32_t size;
 uint8_t method;
 uint8_t status;
 uint8_t type;
 uint8_t server;
};
    """
    def i(name): return (name, '>u4')
    def b(name): return (name, 'b')
    return np.dtype([i('timestamp'),
                     i('client_id'),
                     i('object_id'),
                     i('size'),
                     b('method'),
                     b('status'),
                     b('type'),
                     b('server')])

def read_log(path):
    buf = gzip.open(path, "r").read()
    df = pd.DataFrame(np.frombuffer(buf, dtype=request_type()))
    int64 = df.timestamp.values.astype(np.int64)
    df.timestamp = int64.view("datetime64[s]")
    df.http_version = df.status.apply(lambda x: (x & 0xc0) >> 6)
    df.status = df.status & 0x3f
    df.replace(dict(method=METHODS, type=TYPES, status=STATUS), inplace=True)
    return df

def graphs(df):
    g = df.groupby(df.client_id)
    retention_time = g.nth(-1).timestamp - g.nth(0).timestamp
    import pdb; pdb.set_trace()
    pd.DataFrame(dict(retention_time=retention_time)).boxplot()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.stderr.write("USAGE: %s logfile")
    df = pd.concat([read_log(arg) for arg in sys.argv[1:]])
    graphs(df)
