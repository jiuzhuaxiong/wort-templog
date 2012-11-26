# -*- coding: utf-8 -*-
from utils import L,W,E,EX
import config
import gevent

class Fridge(gevent.Greenlet):

    OVERSHOOT_MAX_DIV = 1800.0 # 30 mins
    FRIDGE_AIR_MIN_RANGE = 4 # ºC
    FRIDGE_AIR_MAX_RANGE = 4

    def __init__(self, server):
        gevent.Greenlet.__init__(self)
        self.server = server
        self.setup_gpio()
        self.wort_valid_clock = 0
        self.fridge_on_clock = 0
        self.fridge_off_clock = 0

    def setup_gpio(self):
        dir_fn = '%s/direction' % config.FRIDGE_GPIO
        with f = open(dir_fn, 'w'):
            f.write('low')
        val_fn = '%s/value' % config.FRIDGE_GPIO
        self.value_file = f.open(val_fn, 'r+')

    def turn(self, value):
        self.value_file.seek(0)
        if value:
            self.value_file.write('1')
        else:
            self.value_file.write('0')
        self.value_file.flush()

    def on(self):
        self.turn(True)

    def off(self):
        self.turn(False)

    def is_on(self):
        self.value_file.seek(0)
        buf = self.value_file.read().strip()
        if buf == '0':
            return False
        if buf != '1':
            E("Bad value read from gpio '%s': '%s'" 
                % (self.value_file.name, buf))
        return True

    # greenlet subclassed
    def _run(self):
        while True:
            self.do()
            gevent.sleep(config.FRIDGE_SLEEP)

    def do(self)
        """ this is the main fridge control logic """
        wort, fridge = self.server.current_temps()

        fridge_min = params.fridge_setpoint - self.FRIDGE_AIR_MIN_RANGE
        fridge_max = params.fridge_setpoint + self.FRIDGE_AIR_MAX_RANGE

        wort_max = params.fridge_setpoint + params.fridge_difference

        off_time = self.server.now() - self.fridge_off_clock

        if off_time < config.FRIDGE_DELAY:
            L("fridge skipping, too early")
            return

        # handle broken wort sensor
        if wort is not None:
            self.wort_valid_clock = self.server.now()
        else:
            W("Invalid wort sensor")
            invalid_time = self.server.now() - self.wort_valid_clock
            if invalid_time < config.FRIDGE_WORT_INVALID_TIME:
                W("Has only been invalid for %d, waiting" % invalid_time)
                return

        if fridge is None:
            W("Invalid fridge sensor")

        if self.is_on():
            turn_off = False
            on_time = self.server.now() - self.fridge_on_clock

            overshoot = 0
            if on_time > params.overshoot_delay:
                overshoot = params.overshoot_factor \
                    * min(self.OVERSHOOT_MAX_DIV, on_time) \
                    / self.OVERSHOOT_MAX_DIV
            L("on_time %(on_time)f, overshoot %(overshoot)f" % locals())

            if wort is not None:
                if (wort - overshoot) < params.fridge_setpoint:
                    L("wort has cooled enough")
                    turn_off = True
            else:
                # wort sensor is broken
                if fridge is not None and fridge < fridge_min:
                    W("fridge off fallback")
                    turn_off = True

            if turn_off:
                L("Turning fridge off")
                self.off()
                self.fridge_off_clock = self.server.now()

        else:
            # fridge is off
            turn_on = False
            if wort is not None:
                if wort >= wort_max:
                    L("Wort is too hot")
                    turn_on = True
            else:
                # wort sensor is broken
                if fridge is not None and fridge >= fridge_max:
                    W("frdge on fallback")
                    turn_on = True

            if turn_on:
                L("Turning fridge on")
                self.on()
                fridge_on_clock = self.server.now()