'''Irrigation zone class'''

import asyncio
import logging
import math
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
import homeassistant.util.dt as dt_util
from homeassistant.core import HomeAssistant
from .const import (
    ATTR_ENABLE_ZONE,
    ATTR_FLOW_SENSOR,
    ATTR_IGNORE_RAIN_SENSOR,
    ATTR_PUMP,
    ATTR_RAIN_SENSOR,
    ATTR_REPEAT,
    ATTR_WAIT,
    ATTR_WATER,
    ATTR_WATER_ADJUST,
    ATTR_ZONE,
    ATTR_ZONE_GROUP,
    CONST_SWITCH,
    CONST_LATENCY,
    CONST_ZERO_FLOW_DELAY
)

_LOGGER = logging.getLogger(__name__)

class IrrigationZone:
    ''' irrigation zone class'''
    def __init__(
        self,
        hass:HomeAssistant,
        zone,
        run_freq,
        hist_flow_rate,
        last_ran,
    ) -> None:
        self.hass = hass
        self._name = zone.get(ATTR_ZONE).split(".")[1]
        self._switch = zone.get(ATTR_ZONE)
        self._pump = zone.get(ATTR_PUMP)
        self._run_freq = run_freq
        self._rain_sensor = zone.get(ATTR_RAIN_SENSOR)
        self._ignore_rain_sensor = zone.get(ATTR_IGNORE_RAIN_SENSOR)
        self._enable_zone = zone.get(ATTR_ENABLE_ZONE)
        self._flow_sensor = zone.get(ATTR_FLOW_SENSOR)
        self._hist_flow_rate = hist_flow_rate
        self._water = zone.get(ATTR_WATER)
        self._water_adjust = zone.get(ATTR_WATER_ADJUST)
        self._wait = zone.get(ATTR_WAIT)
        self._repeat = zone.get(ATTR_REPEAT)
        self._zone_group = zone.get(ATTR_ZONE_GROUP)
        self._last_ran = last_ran
        self._remaining_time = 0
        self._state = "off"
        self._stop = False

    def name(self):
        """Return the name of the variable."""
        return self._name

    def switch(self):
        """Return the name of the variable."""
        return self._switch

    def pump(self):
        ''' Pump entity attribute'''
        return self._pump

    def run_freq(self):
        '''run frequency enity attribute'''
        return self._run_freq

    def run_freq_value(self):
        '''run frequancy entity value'''
        run_freq_value = None
        if self._run_freq is not None:
            if self.hass.states.get(self._run_freq) is None:
                _LOGGER.error(
                    "Run_freq: %s not found, check your configuration", self._run_freq
                )
            else:
                run_freq_value = self.hass.states.get(self._run_freq).state
        return run_freq_value

    def rain_sensor(self):
        '''rain sensor entity attribute'''
        return self._rain_sensor

    def rain_sensor_value(self):
        ''' rain sensor entity value'''
        rain_sensor_value = False
        if self._rain_sensor is not None:
            if self.hass.states.get(self._rain_sensor) is None:
                _LOGGER.error(
                    "Rain sensor: %s not found, check your configuration",
                    self._rain_sensor,
                )
            else:
                rain_sensor_value = self.hass.states.is_state(
                    self._rain_sensor, "on"
                )
        return rain_sensor_value

    def ignore_rain_sensor(self):
        '''ignore rain sensor entity attribute'''
        return self._ignore_rain_sensor

    def ignore_rain_sensor_value(self):
        ''' rain sensor value'''
        ignore_rain_sensor_value = False
        if self._ignore_rain_sensor is not None:
            ignore_rain_sensor_value = self.hass.states.is_state(
                self._ignore_rain_sensor, "on"
            )
        return ignore_rain_sensor_value

    def water_adjust(self):
        '''water adjustment entity attribute'''
        return self._water_adjust

    def water_adjust_value(self):
        '''determine watering adjustment'''
        water_adjust_value = 1
        if self._water_adjust is not None:
            water_adjust_value = float(self.hass.states.get(self._water_adjust).state)
        return water_adjust_value

    def flow_sensor(self):
        '''flow sensor attribute'''
        return self._flow_sensor

    def flow_sensor_value(self):
        '''flow sensor attributes value'''
        flow_value = None
        if self._flow_sensor is not None:
            flow_value = float(self.hass.states.get(self._flow_sensor).state)
        return flow_value

    def flow_rate(self):
        '''history flow attribute'''
        if self.flow_sensor_value() > 0:
            return self.flow_sensor_value()
        #else use the historical value
        return self._hist_flow_rate

    def water(self):
        '''water entity attribute'''
        return self._water

    def water_value(self):
        '''water attibute value'''
        return float(self.hass.states.get(self._water).state)

    def wait(self):
        '''waith entity attribute'''
        return self._wait

    def wait_value(self):
        ''' wait entity value'''
        wait_value = 0
        if self._wait is not None:
            wait_value = float(self.hass.states.get(self._wait).state)
        return wait_value

    def repeat(self):
        '''repeat entity attribute'''
        return self._repeat

    def repeat_value(self):
        ''' repeat entity value'''
        repeat_value = 1
        if self._repeat is not None:
            repeat_value = int(float(self.hass.states.get(self._repeat).state))
            if repeat_value == 0:
                repeat_value = 1
        return repeat_value

    def state(self):
        ''' state value'''
        return self._state

    def zone_group(self):
        '''zone group entity attribute'''
        return self._zone_group

    def zone_group_value(self):
        '''zone group entity value'''
        zone_group_value = None
        if self._zone_group is not None:
            zone_group_value = self.hass.states.get(self._zone_group).state
        return zone_group_value

    def enable_zone(self):
        '''enable zone entity attribute'''
        return self._enable_zone

    def enable_zone_value(self):
        '''enable zone entity value'''
        zone_value = 'on'
        if self._enable_zone is not None:
            zone_value = self.hass.states.is_state(self._enable_zone, "on")
        return zone_value

    def remaining_time(self):
        """remaining time or remaining volume"""
        return self._remaining_time

    def run_time(self, seconds_run=0, volume_delivered=0, repeats=1, scheduled=False, water_adjustment=1):
        """update the run time component"""

        wait = self.wait_value()*60
        #if run manually do not adjust the time
        if scheduled:
            adjust = water_adjustment
        else:
            adjust = 1

        if self._flow_sensor is None:
            #time based
            water = self.water_value()*60
            run_time = (water * adjust * repeats) + (wait * (repeats -1))
        else:
            #volume based/flow sensor
            water = self.water_value() #volume
            flow = self.flow_rate() # flow rate
            delivery_volume = water * adjust
            if volume_delivered > 0: # the cycle has started
                remaining_volume = (delivery_volume * (repeats-1)) +  delivery_volume - volume_delivered
            else:
                remaining_volume = delivery_volume * repeats

            watertime = remaining_volume / flow * 60
            #remaining watering time + remaining waits
            run_time = watertime + (wait * (repeats -1))

        run_time = run_time - seconds_run
        # zone has been disabled
#        if self.enable_zone_value() is False or adjust == 0:
#            run_time = 0
        return math.ceil(run_time)

    def last_ran(self):
        '''last ran datetime attribute'''
        return self._last_ran

    def is_raining(self):
        """assess the rain_sensor including ignore rain_sensor"""
        if self.ignore_rain_sensor_value():
            return False
        else:
            return self.rain_sensor_value()

    def should_run(self, scheduled=False):
        '''determine if the zone should run'''
        if not (self.hass.states.is_state(self._switch, "on") or self.hass.states.is_state(self._switch, "off")):
            #Switch is unavavailable
            _LOGGER.warning("Zone switch %s is offline", self.switch())
            return False
        #zone is disabled
        if not self.enable_zone_value():
            return False

        if self.water_adjust_value() == 0 and scheduled is True:
            return False

        #no Frequency provided
        if self.run_freq_value() is None:
            return True

        # Only stop the zone if it is a scheduled run
        if self.is_raining() is True and scheduled is True:
            return False

        last_ran_relative = 0
        if self._last_ran:
            #how long since the zone last ran in days
            last_ran_relative = float(
                (
                    (
                        dt_util.as_timestamp(dt_util.now())
                        - dt_util.as_timestamp(self._last_ran)
                    )
                    #adjust by 10 minutes to allow for any variances
                    + 600
                )
                / 86400
            )

        if self.run_freq_value().isnumeric():
            numeric_freq = int(float(self.run_freq_value()))
            if numeric_freq <= last_ran_relative or not self._last_ran:
                return True
            if scheduled: return False
            #this is a manual request
            return True
        else:
            string_freq = self.run_freq_value()
            string_freq = string_freq.replace(" ","").replace("'","").strip("[]'").split(",")
            string_freq = [x.capitalize() for x in string_freq]
            #if the day is found in the frequency
            if dt_util.now().strftime("%a") in string_freq:
                #found today in the frequency
                return True
            #Not today, now check if there is an invalid data i.e. off
            valid_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            valid_freq = any(item in string_freq for item in valid_days)
            #the frequency is a list of valid days
            #if this a scheduled run or not a valid freq do not run
            if scheduled is True or valid_freq is False: return False
            #this is a manual request
            return True

    # end should_run

    def check_switch_state(self):
        """ check the solenoid state if turned off stop this instance"""
        if self.hass.states.is_state(self._switch, "off"):
            return False
        return True

    async def async_turn_on(self, scheduled=False):
        """start the watering cycle """
        stop = False
        self._stop = False

        #initalise the reamining time for display
        if scheduled is True:
            water_adjust_value = self.water_adjust_value()
        else:
            water_adjust_value = 1

        self._remaining_time = self.run_time(repeats=self.repeat_value(), scheduled=scheduled, water_adjustment=water_adjust_value)
        # run the watering cycle, water/wait/repeat
        zeroflowcount = 0
        for i in range(self.repeat_value(), 0, -1):
            seconds_run = 0
            #run time adjusted to 0 skip this zone
            if self._remaining_time <= 0:
                continue
            self._state = "on"
            await asyncio.sleep(1)
            if self.check_switch_state() is False and stop is False:
                await self.hass.services.async_call(
                    CONST_SWITCH, SERVICE_TURN_ON, {ATTR_ENTITY_ID: self._switch}
                )

            #track the watering
            if self._flow_sensor is not None:
                volume_remaining = self.water_value() * water_adjust_value
                volume_delivered = 0
                while volume_remaining > 0:
                    volume_delivered += self.flow_sensor_value() / 60
                    volume_required = self.water_value() * water_adjust_value
                    volume_remaining = volume_required - volume_delivered
                    self._remaining_time = self.run_time(volume_delivered=volume_delivered, repeats=i, scheduled=scheduled, water_adjustment=water_adjust_value)
                    await asyncio.sleep(1)
                    #flow sensor has failed or no water is being provided
                    if self.flow_sensor_value() == 0:
                        zeroflowcount += 1
                        stop = True
                        if zeroflowcount > CONST_ZERO_FLOW_DELAY:
                            _LOGGER.warning("No flow detected for %s seconds, turning off solenoid to allow program to complete",CONST_ZERO_FLOW_DELAY)
                            break
                    else:
                        zeroflowcount = 0
            else:
                watertime = math.ceil(self.water_value()*60 * water_adjust_value)
                while watertime > 0:
                    seconds_run += 1
                    watertime = math.ceil(self.water_value()*60 * water_adjust_value) - seconds_run
                    self._remaining_time = self.run_time(seconds_run, repeats=i, scheduled=scheduled, water_adjustment=water_adjust_value)
                    await asyncio.sleep(1)

            if stop or self._stop:
                break
            #Eco mode, wait cycle
            if self.wait_value() > 0 and i > 1:
                self._state = "eco"
                await self.async_eco_off()
                waittime = self.wait_value() * 60
                wait_seconds = 0
                while waittime > 0:
                    seconds_run += 1
                    wait_seconds += 1
                    waittime = self.wait_value() * 60 - wait_seconds
                    self._remaining_time = self.run_time(seconds_run, repeats=i, scheduled=scheduled, water_adjustment=water_adjust_value)
                    if stop or self._stop:
                        break
                    await asyncio.sleep(1)

            if stop or self._stop:
                break
        # End of repeat loop
        await self.async_turn_off()

    async def async_eco_off(self, **kwargs):
        '''signal the zone to stop'''
        await self.hass.services.async_call(
            CONST_SWITCH, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: self._switch}
        )
        latency = await self.latency_check()
        #raise an event
        event_data = {
            "action": "zone_turned_off",
            "device_id": self._switch,
            "zone": self._name,
            "state":"eco",
            "latency": latency
        }
        self.hass.bus.async_fire("irrigation_event", event_data)
        self._state = "eco"

    async def async_turn_off(self, **kwargs):
        '''signal the zone to stop'''
        self._state = "off"
        self._stop = True
        self._remaining_time = 0
        await self.hass.services.async_call(
            CONST_SWITCH, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: self._switch}
        )
        #raise an event
        latency = await self.latency_check()
        event_data = {
            "action": "zone_turned_off",
            "device_id": self._switch,
            "zone": self._name,
            "state":"off",
            "latency": latency
        }
        self.hass.bus.async_fire("irrigation_event", event_data)

    async def latency_check(self):
        '''Ensure switch has turned off and warn'''
        for i in range(CONST_LATENCY):
            if self.check_switch_state() is True: #on
                await asyncio.sleep(1)
            else:
                return False
        _LOGGER.warning('Switch has excesive latency, exceding %s seconds, cannot confirm %s is off', i+1, self._switch)
        return True

    def set_last_ran(self, last_ran):
        '''update the last ran attribute'''
        self._last_ran = last_ran

    def validate(self, **kwargs):
        '''validate inputs'''
        valid = True
        if self._switch is not None and self.hass.states.async_available(self._switch):
            _LOGGER.error("%s not found switch", self._switch)
            valid = False
        if self._pump is not None and self.hass.states.async_available(self._pump):
            _LOGGER.error("%s not found pump", self._pump)
            valid = False
        if self._run_freq is not None and self.hass.states.async_available(
            self._run_freq):
            _LOGGER.error("%s not found run frequency" , self._run_freq)
            valid = False
        if self._rain_sensor is not None and self.hass.states.async_available(
            self._rain_sensor):
            _LOGGER.error("%s not found rain sensor", self._rain_sensor)
            valid = False
        if self._flow_sensor is not None and self.hass.states.async_available(
            self._flow_sensor):
            _LOGGER.error("%s not found flow sensor", self._flow_sensor)
            valid = False
        if self._water_adjust is not None and self.hass.states.async_available(
            self._water_adjust):
            _LOGGER.error("%s not found adjustment", self._water_adjust)
            valid = False
        return valid

    async def async_test_zone(self):
        '''Show simulation results'''
        _LOGGER.warning("----------------------------")
        _LOGGER.warning("Zone:                     %s", self._name)
        _LOGGER.warning("Should run:               %s", self.should_run())
        _LOGGER.warning("Last Run time:            %s", self._last_ran)
        _LOGGER.warning("Run time:                 %s", self.run_time(repeats=self.repeat_value()))
        _LOGGER.warning("Water Value:              %s", self.water_value())
        _LOGGER.warning("Wait Value:               %s", self.wait_value())
        _LOGGER.warning("Repeat Value:             %s", self.repeat_value())
        _LOGGER.warning("Rain sensor value:        %s", self.rain_sensor_value())
        _LOGGER.warning("Ignore rain sensor Value: %s", self.ignore_rain_sensor_value())
        _LOGGER.warning("Run frequency Value:      %s", self.run_freq_value())
        _LOGGER.warning("Flow Sensor Value:        %s", self.flow_sensor_value())
        _LOGGER.warning("Adjuster Value:           %s", self.water_adjust_value())
