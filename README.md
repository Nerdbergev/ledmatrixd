# ledmatrixd

A python client that will control the LED matrix that's hanging in
the Nerdberg hacker space.

https://twitter.com/NerdbergEV/status/1457238769220849666

The hardware is a LED sign from a subway train that was donated
to the hacker space, and ints innards (control computer) were replaced
by small PCB with a stm32 controller. This hardware is documented here:

https://github.com/vogelchr/subway_led_panel_stm32f103

This software is still in active development as of January 2022.

## Quick start

This daemon can be run in two ways:

    ./run_ledmatrixd_sim.sh

Which creates a python virtualenv, installs (besides other things) pygame,
and pops up a small window showing a simulated USB matrix. This is useful
for development. The other alternative is

    ./run_ledmatrixd_usb.sh

...which tries to connect to the real device using USB, and runs it in
a python virtualenv that has pyusb installed.

(this translates to the "-S" simulation argument of pymatrixd.)


## MQTT

MQTT Messages received as json objects in the subscribed topic:

_Turn the LED sign off (currently unimplemented)_

    {
        'command': 'off'
    }

_Turn the LED sign on (currently unimplemented)_

    {
        'command': 'on'
    }

_Replace the main (in canvas #0)_

    {
        'command': 'write',
        'text': 'string you want to replace'
        'direction': pixels per 60th second
    }
