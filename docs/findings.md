# Findings

- WaveShare Pico-ResTouch-LCD-2.8 (WAVESHARE-19804) is an IPS SPI display with ST7789 driver, XPT2046 resistive touch controller, MicroSD slot, and onboard Pico header. Source: https://www.waveshare.com/pico-restouch-lcd-2.8.htm and https://www.waveshare.com/wiki/Pico-ResTouch-LCD-2.8 .
- Communication decision: use MicroPython socket client over Wi-Fi with JSON commands from Raspberry Pi 5 (TCP server). USB is only for power. Documentation now references this architecture.
- Required display modes: date/weather/temperature/time overview and short task list currently; JPEG background support also needed.
