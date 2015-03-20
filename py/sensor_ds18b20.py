#!/usr/bin/env python2.7

import os
import re
import asyncio
import concurrent.futures

import config
from utils import D,L,W,E,EX

class DS18B20s(object):

    THERM_RE = re.compile('.* YES\n.*t=(.*)\n', re.MULTILINE)

    def __init__(self, server):
        self.server = server
        self.readthread = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.master_dir = config.SENSOR_BASE_DIR

    @asyncio.coroutine
    def do(self):
        vals = {}
        for n in self.sensor_names():
                value = yield from self.do_sensor(n)
                if value is not None:
                    vals[n] = value

        itemp = self.do_internal()
        if itemp:
            vals['internal'] = itemp

        self.server.add_reading(vals)

    @asyncio.coroutine
    def run(self):
        while True:
            yield from self.do()
            yield from self.server.sleep(config.SENSOR_SLEEP)

    @asyncio.coroutine
    def read_wait(self, f):
        # handles a blocking file read with a threadpool. A
        # real python thread performs the read while other 
        # asyncio tasks keep running.
        # the ds18b20 takes ~750ms to read, which is noticable
        # interactively.
        loop = asyncio.get_event_loop()
        yield from loop.run_in_executor(self.readthread, f.read)

    @asyncio.coroutine
    def do_sensor(self, s, contents = None):
        """ contents can be set by the caller for testing """
        try:
            if contents is None:
                fn = os.path.join(self.master_dir, s, 'w1_slave')
                f = open(fn, 'r')
                contents = yield from self.read_wait(f)

            match = self.THERM_RE.match(contents)
            if match is None:
                D("no match")
                return None
            temp = int(match.groups(1)[0]) / 1000.0
            if temp > 80:
                E("Problem reading sensor '%s': %f" % (s, temp))
                return None
            return temp
        except Exception, e:
            EX("Problem reading sensor '%s': %s" % (s, str(e)))
            return None

    def do_internal(self):
        try:
            return int(open(config.INTERNAL_TEMPERATURE, 'r').read()) / 1000.0
        except Exception, e:
            EX("Problem reading internal sensor: %s" % str(e))
            return None
        

    def sensor_names(self):
        """ Returns a sequence of sensorname """
        slaves_path = os.path.join(self.master_dir, "w1_master_slaves")
        contents = open(slaves_path, 'r').read()
        if 'not found' in contents:
            E("No W1 sensors found")
            return []
        names = contents.split()
        return names

    def wort_name(self):
        return config.WORT_NAME

    def fridge_name(self):
        return config.FRIDGE_NAME
